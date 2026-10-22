from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest

from app.config import Settings
from app.llm.openai_compatible import LLMError, OpenAICompatibleLLM
from app.pipeline.orchestrator import AgentPipeline
from app.state import new_state
from app.tools.base import PageReader, QuerySpec, ReadResult, SearchHit, SearchTool
from app.tools.reader import SafePageReader
from app.tools.search import (
    DeepSeekSearchTool,
    TavilySearchTool,
    build_deepseek_query,
)


class FixedSearch(SearchTool):
    def __init__(self, hits):
        self.hits = hits

    def search(self, spec: QuerySpec, *, window: str, limit: int):
        return self.hits[:limit]


class FixedReader(PageReader):
    def __init__(self, result):
        self.result = result

    def read(self, url: str, *, timeout_seconds: float | None = None):
        return self.result


class FixedLLM:
    def __init__(self, extraction):
        self.extraction = extraction

    def plan_queries(self, context):
        return (
            {
                "queries": [
                    {
                        "text": "Agent release notes",
                        "purpose": "发现 Agent 项目近期发布",
                        "strategy": "official",
                        "topic": context["topics"][0],
                        "language": "en",
                        "domains": [],
                    }
                ],
                "notes": "fixed",
            },
            {"tokens_in": 10, "tokens_out": 5},
        )

    def extract_events(self, context):
        return self.extraction, {"tokens_in": 20, "tokens_out": 10}

    def analyze_gaps(self, context):
        return {"gaps": [], "notes": ""}, {"tokens_in": 5, "tokens_out": 2}


def _settings(tmp_path, **overrides):
    return Settings(
        data_dir=tmp_path,
        db_path=tmp_path / "adapter.sqlite3",
        seed_demo_on_start=False,
        demo_step_delay_seconds=0,
        **overrides,
    )


def _state(settings, mode="demo"):
    return new_state(
        run_id="run_adapter",
        mode=mode,
        topics=["Agent"],
        window="week",
        settings=settings,
        now=datetime.now(settings.tz),
    )


def test_live_mode_counts_daily_usage_with_fake_adapters(tmp_path, repo):
    settings = _settings(tmp_path)
    state = _state(settings, "live")
    repo.create_run(state)
    from app.demo import build_demo_bundle

    now = datetime.now(settings.tz)
    search, reader, llm, _corpus = build_demo_bundle(now)
    pipeline = AgentPipeline(
        settings=settings,
        repo=repo,
        search_tool=search,
        reader=reader,
        llm=llm,
        now=now,
        delay_seconds=0,
    )
    pipeline.run(state)
    assert state["status"] == "completed"
    assert state["usage"]["remote_calls"] > 0
    usage = repo.recent_usage(pipeline.budget.day)
    assert usage["search_calls"] > 0
    assert usage["model_calls"] > 0


def test_read_failure_preserves_no_fabricated_events(tmp_path, repo):
    settings = _settings(tmp_path, max_gap_rounds=0)
    state = _state(settings)
    repo.create_run(state)
    search = FixedSearch(
        [
            SearchHit(
                title="Unreadable page",
                url="https://example.com/unreadable",
                snippet="snippet only",
                domain="example.com",
                score=0.8,
            )
        ]
    )
    reader = FixedReader(ReadResult(ok=False, url="https://example.com/unreadable", error="读取超时"))
    llm = FixedLLM({"events": [], "notes": ""})
    pipeline = AgentPipeline(
        settings=settings,
        repo=repo,
        search_tool=search,
        reader=reader,
        llm=llm,
        now=datetime.now(settings.tz),
        delay_seconds=0,
    )
    pipeline.run(state)
    assert state["events"] == []
    assert state["status"] == "partial"
    assert state["stop_reason"] == "read_failed"
    assert repo.get_run_events(state["id"]) == []


def test_unmatched_quote_is_not_promoted_to_a_fact(tmp_path, repo):
    settings = _settings(tmp_path, max_gap_rounds=0)
    state = _state(settings)
    repo.create_run(state)
    search = FixedSearch(
        [
            SearchHit(
                title="Agent release",
                url="https://example.com/release",
                snippet="snippet only",
                domain="example.com",
                score=0.9,
            )
        ]
    )
    reader = FixedReader(
        ReadResult(
            ok=True,
            url="https://example.com/release",
            final_url="https://example.com/release",
            title="Agent release",
            content="这是一篇真实的正文，但没有模型引用的那句话。",
            published_at="2026-10-20",
        )
    )
    llm = FixedLLM(
        {
            "events": [
                {
                    "event_key": "fake:1",
                    "title": "An event",
                    "project": "Fake",
                    "topic": "Agent",
                    "event_type": "release",
                    "event_date": "2026-10-20",
                    "date_confidence": "confirmed",
                    "summary": "摘要",
                    "confidence": "high",
                    "facts": [
                        {
                            "statement": "模型编造的事实。",
                            "category": "release",
                            "conditions": "",
                            "evidence": [
                                {"document_id": "d1", "quote": "正文里根本不存在的句子。"}
                            ],
                        }
                    ],
                    "unresolved": [],
                    "primary_document_id": "d1",
                }
            ]
        }
    )
    pipeline = AgentPipeline(
        settings=settings,
        repo=repo,
        search_tool=search,
        reader=reader,
        llm=llm,
        now=datetime.now(settings.tz),
        delay_seconds=0,
    )
    pipeline.run(state)
    assert state["events"] == []
    assert state["status"] == "completed"
    assert state["stop_reason"] == "no_verifiable_events"
    assert state["verification"]["facts_supported"] == 0
    assert state["verification"]["evidence_verified"] == 0


def test_model_auth_failure_stops_before_search(tmp_path, repo):
    settings = _settings(tmp_path, max_gap_rounds=0)
    state = _state(settings)
    repo.create_run(state)

    class AuthFailureLLM:
        def plan_queries(self, context):
            raise LLMError("鉴权失败", code="llm_auth")

        def extract_events(self, context):
            raise AssertionError("extraction must not run after auth failure")

        def analyze_gaps(self, context):
            raise AssertionError("gap analysis must not run after auth failure")

    class CountingSearch(SearchTool):
        def __init__(self):
            self.calls = 0

        def search(self, spec, *, window, limit):
            self.calls += 1
            return []

    search = CountingSearch()
    pipeline = AgentPipeline(
        settings=settings,
        repo=repo,
        search_tool=search,
        reader=FixedReader(ReadResult(ok=False, url="", error="unused")),
        llm=AuthFailureLLM(),
        now=datetime.now(settings.tz),
        delay_seconds=0,
    )
    pipeline.run(state)
    assert state["status"] == "failed"
    assert search.calls == 0
    assert state["usage"]["model_calls"] == 1
    assert state["stop_reason"] == "service_unavailable"


def test_tavily_adapter_disables_service_answer_and_passes_window(tmp_path):
    settings = _settings(tmp_path, tavily_api_key="test-key")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Official release",
                        "url": "https://example.com/release",
                        "content": "snippet",
                        "score": 0.9,
                        "published_date": "2026-10-20",
                    }
                ]
            },
        )

    client = TavilySearchTool(settings, transport=httpx.MockTransport(handler))
    hits = client.search(
        QuerySpec(
            text="agent release",
            purpose="official release",
            strategy="official",
            topic="Agent",
            domains=["example.com"],
        ),
        window="week",
        limit=5,
    )
    assert captured["include_answer"] is False
    assert captured["include_raw_content"] is False
    assert captured["time_range"] == "week"
    assert captured["include_domains"] == ["example.com"]
    assert hits[0].domain == "example.com"
    client.close()


def test_deepseek_search_maps_time_domains_and_results(tmp_path):
    settings = _settings(
        tmp_path,
        search_provider="deepseek",
        llm_base_url="https://api.deepseek.com",
        llm_api_key="test-deepseek-key",
        llm_model="deepseek-flash",
    )
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.deepseek.com/v1/tools/search"
        assert request.headers["authorization"] == "Bearer test-deepseek-key"
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "rerank_score": 2.4,
                        "title": "DeepSeek release",
                        "url": "https://example.com/deepseek",
                        "snippet": "A short result snippet.",
                        "summary": "Longer summary.",
                        "date": "2026-10-20T00:00:00+00:00",
                    }
                ]
            },
        )

    client = DeepSeekSearchTool(settings, transport=httpx.MockTransport(handler))
    hits = client.search(
        QuerySpec(
            text="DeepSeek release",
            purpose="official release",
            strategy="official",
            topic="Agent",
            domains=["example.com"],
        ),
        window="week",
        limit=5,
    )
    assert "after:" in captured["query"]
    assert "site:example.com" in captured["query"]
    assert len(captured["query"]) <= 128
    assert captured["count"] == 5
    assert captured["need_content"] is False
    assert hits[0].domain == "example.com"
    assert hits[0].score == pytest.approx(0.8)
    client.close()


def test_deepseek_search_balance_error_is_not_retried(tmp_path):
    settings = _settings(
        tmp_path,
        search_provider="deepseek",
        llm_base_url="https://api.deepseek.com",
        llm_api_key="test-deepseek-key",
        llm_model="deepseek-flash",
    )

    client = DeepSeekSearchTool(
        settings,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(402, json={"error": {"message": "balance"}})
        ),
    )
    with pytest.raises(Exception) as error:
        client.search(
            QuerySpec(text="test", purpose="test", strategy="open", topic="Agent"),
            window="day",
            limit=5,
        )
    assert getattr(error.value, "code", "") == "search_balance"
    assert getattr(error.value, "transient", True) is False
    client.close()


def test_deepseek_provider_readiness_requires_only_model_key(tmp_path):
    settings = _settings(
        tmp_path,
        search_provider="deepseek",
        llm_base_url="https://api.deepseek.com",
        llm_api_key="test-key",
        llm_model="deepseek-flash",
    )
    assert settings.live_ready is True
    assert settings.live_missing == []
    settings.llm_api_key = ""
    assert settings.live_missing == ["LLM_API_KEY"]


def test_deepseek_query_never_exceeds_api_limit(tmp_path):
    settings = _settings(tmp_path)
    spec = QuerySpec(
        text="超长查询" * 40,
        purpose="test",
        strategy="open",
        topic="Agent",
        domains=["a-very-long-official-domain.example.com"],
    )
    query = build_deepseek_query(spec, window="day", now=datetime.now(settings.tz))
    assert len(query) <= 128
    assert "after:" in query


def test_openai_compatible_adapter_validates_json(tmp_path):
    settings = _settings(
        tmp_path,
        llm_base_url="https://llm.example/v1",
        llm_api_key="secret-key",
        llm_model="test-model",
        llm_thinking="disabled",
    )
    plan = {
        "queries": [
            {
                "text": "Agent release",
                "purpose": "find release",
                "strategy": "official",
                "topic": "Agent",
                "language": "en",
                "domains": [],
            }
        ],
        "notes": "ok",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Bearer ")
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(plan)}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            },
        )

    client = OpenAICompatibleLLM(settings, transport=httpx.MockTransport(handler))
    data, usage = client.plan_queries(
        {"now": "2026-10-21T12:00+08:00", "timezone": "Asia/Shanghai", "days": 7, "topics": ["Agent"], "limit": 5}
    )
    assert data["queries"][0]["text"] == "Agent release"
    assert usage == {"tokens_in": 12, "tokens_out": 7}
    client.close()


def test_page_reader_extracts_content_and_blocks_private_redirect(tmp_path, monkeypatch):
    import app.tools.reader as reader_module

    settings = _settings(tmp_path)
    html = b"""<html lang="zh"><head><title>Test page</title>
    <meta property="article:published_time" content="2026-10-20T08:00:00Z"></head>
    <body><nav>menu</nav><article><h1>Headline</h1>
    <p>This is a sufficiently long paragraph about an agent release with details.</p>
    <p>Another paragraph with compatibility information and test conditions.</p>
    </article></body></html>"""
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=html)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    monkeypatch.setattr(reader_module, "safe_public_url", lambda url: (True, ""))
    client = SafePageReader(settings, transport=httpx.MockTransport(handler))
    result = client.read("https://example.com/article")
    assert result.ok
    assert result.title == "Headline"
    assert "compatibility information" in result.content
    assert result.published_at == "2026-10-20"
    assert "menu" not in result.content
    client.close()

    def redirect_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    monkeypatch.setattr(
        reader_module,
        "safe_public_url",
        lambda url: (False, "链接指向本机或内网地址") if "127.0.0.1" in url else (True, ""),
    )
    redirect_reader = SafePageReader(settings, transport=httpx.MockTransport(redirect_handler))
    blocked = redirect_reader.read("https://example.com/redirect")
    assert not blocked.ok
    assert "内网" in blocked.error
    redirect_reader.close()
