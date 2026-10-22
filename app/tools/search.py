from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from ..config import Settings
from ..security import display_domain
from .base import QuerySpec, SearchHit, SearchTool, ToolError

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEEPSEEK_QUERY_MAX = 128


class TavilySearchTool(SearchTool):
    """Small adapter around Tavily Search. Answer generation is always disabled."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        if not settings.tavily_api_key:
            raise ToolError("TAVILY_API_KEY 未配置", code="config_missing")
        self.settings = settings
        self._client = httpx.Client(
            timeout=httpx.Timeout(22.0, connect=8.0),
            headers={"User-Agent": "SignalField/0.1 (local research assistant)"},
            transport=transport,
        )

    def search(self, spec: QuerySpec, *, window: str, limit: int) -> list[SearchHit]:
        payload = {
            "api_key": self.settings.tavily_api_key,
            "query": spec.text,
            "topic": "general",
            "search_depth": "basic",
            "max_results": max(1, min(limit, 10)),
            "time_range": "day" if window == "day" else "week",
            # The service answer is intentionally disabled: evidence must come
            # from pages this project actually reads.
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }
        if spec.domains:
            payload["include_domains"] = spec.domains
        try:
            response = self._client.post(TAVILY_SEARCH_URL, json=payload)
        except httpx.TimeoutException as exc:
            raise ToolError("搜索服务超时", transient=True, code="search_timeout") from exc
        except httpx.HTTPError as exc:
            raise ToolError("无法连接搜索服务", transient=True, code="search_network") from exc

        if response.status_code in {401, 403}:
            raise ToolError("搜索服务鉴权失败，请检查服务端密钥", code="search_auth")
        if response.status_code == 429:
            raise ToolError("搜索服务触发限流", transient=True, code="search_rate_limited")
        if response.status_code >= 500:
            raise ToolError("搜索服务暂时不可用", transient=True, code="search_unavailable")
        if response.status_code >= 400:
            raise ToolError(f"搜索请求失败（HTTP {response.status_code}）", code="search_bad_request")
        try:
            data = response.json()
        except ValueError as exc:
            raise ToolError("搜索服务返回了无法解析的数据", code="search_bad_json") from exc

        results = data.get("results")
        if not isinstance(results, list):
            raise ToolError("搜索服务返回格式异常", code="search_bad_shape")
        hits: list[SearchHit] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            domain = display_domain(url)
            snippet = str(item.get("content") or "").strip()[:900]
            score = item.get("score", 0)
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.0
            published = item.get("published_date") or item.get("published")
            hits.append(
                SearchHit(
                    title=title[:240],
                    url=url,
                    snippet=snippet,
                    score=max(0.0, min(score, 1.0)),
                    published_date=str(published)[:40] if published else None,
                    domain=domain,
                )
            )
        return hits

    def close(self) -> None:
        self._client.close()


def build_deepseek_query(spec: QuerySpec, *, window: str, now: datetime) -> str:
    """Map the project's time/domain constraints onto DeepSeek search syntax.

    DeepSeek Search does not expose separate time_range/include_domains fields,
    so the documented ``after:`` and ``site:`` operators are used. The final
    string must stay within the API's 128-character query limit.
    """
    days = 1 if window == "day" else 7
    after = (now - timedelta(days=days)).date().isoformat()
    operators = [f"after:{after}"]
    domains = [domain for domain in spec.domains if domain]
    if domains:
        operators.append(" OR ".join(f"site:{domain}" for domain in domains))
    suffix = " " + " ".join(operators)
    room = DEEPSEEK_QUERY_MAX - len(suffix)
    if room < 2:
        return spec.text.strip()[:DEEPSEEK_QUERY_MAX]
    base = spec.text.strip()[:room].rstrip()
    return f"{base}{suffix}"


class DeepSeekSearchTool(SearchTool):
    """DeepSeek's native search API, sharing auth with the chat model."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        if not settings.llm_api_key:
            raise ToolError("LLM_API_KEY 未配置，无法调用 DeepSeek Search", code="config_missing")
        if not settings.llm_base_url:
            raise ToolError("LLM_BASE_URL 未配置，无法调用 DeepSeek Search", code="config_missing")
        self.settings = settings
        self.endpoint = settings.deepseek_search_url
        self._client = httpx.Client(
            timeout=httpx.Timeout(22.0, connect=8.0),
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "SignalField/0.1 (local research assistant)",
            },
            transport=transport,
        )

    def search(self, spec: QuerySpec, *, window: str, limit: int) -> list[SearchHit]:
        query = build_deepseek_query(
            spec, window=window, now=datetime.now(self.settings.tz)
        )
        payload = {
            "query": query,
            "count": max(1, min(limit, 10)),
            # Full-page content is deliberately not requested here. The project
            # reads and verifies pages itself; search summaries stay discovery-only.
            "need_content": False,
        }
        try:
            response = self._client.post(self.endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise ToolError("DeepSeek 搜索超时", transient=True, code="search_timeout") from exc
        except httpx.HTTPError as exc:
            raise ToolError("无法连接 DeepSeek 搜索服务", transient=True, code="search_network") from exc

        if response.status_code in {401, 403}:
            raise ToolError("DeepSeek 搜索鉴权失败，请检查 LLM_API_KEY", code="search_auth")
        if response.status_code == 402:
            raise ToolError("DeepSeek 账户余额不足，搜索未执行", code="search_balance")
        if response.status_code == 429:
            raise ToolError("DeepSeek 搜索触发限流", transient=True, code="search_rate_limited")
        if response.status_code in {408, 504}:
            raise ToolError("DeepSeek 搜索超时", transient=True, code="search_timeout")
        if response.status_code >= 500:
            raise ToolError("DeepSeek 搜索服务暂时不可用", transient=True, code="search_unavailable")
        if response.status_code >= 400:
            raise ToolError(
                f"DeepSeek 搜索请求失败（HTTP {response.status_code}）",
                code="search_bad_request",
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ToolError("DeepSeek 搜索返回了无法解析的数据", code="search_bad_json") from exc
        results = data.get("results")
        if not isinstance(results, list):
            raise ToolError("DeepSeek 搜索返回格式异常", code="search_bad_shape")

        hits: list[SearchHit] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            snippet = str(item.get("snippet") or item.get("summary") or "").strip()[:900]
            raw_score = item.get("rerank_score", 0)
            try:
                score = float(raw_score) / 3.0
            except (TypeError, ValueError):
                score = 0.0
            published = item.get("date")
            hits.append(
                SearchHit(
                    title=title[:240],
                    url=url,
                    snippet=snippet,
                    score=max(0.0, min(score, 1.0)),
                    published_date=str(published)[:40] if published else None,
                    domain=display_domain(url),
                )
            )
        return hits

    def close(self) -> None:
        self._client.close()
