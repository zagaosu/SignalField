from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from ..budgets import (
    BudgetController,
    BudgetError,
    CancelledError,
    DailyBudgetExceeded,
    RunBudgetExceeded,
    TimeBudgetExceeded,
)
from ..config import Settings
from ..db import Repository
from ..models import TOPIC_PRESETS, iso_now, parse_event_date
from ..pipeline.evidence import (
    contains_conflict,
    content_hash,
    document_priority,
    event_too_old,
    fact_has_missing_conditions,
    is_near_duplicate,
    merge_event,
    normalize_key,
    normalize_ws,
    quote_verified,
    same_event,
)
from ..security import canonical_url, display_domain, quick_url_check
from ..state import add_warning, mark_done, set_stage
from ..tools.base import LLMClient, PageReader, QuerySpec, SearchTool, ToolError

logger = logging.getLogger(__name__)

TOPIC_KEYWORDS = {
    "Agent": ("agent", "智能体", "工具调用", "编排", "记忆", "评测"),
    "推理部署": ("推理", "inference", "量化", "quant", "端侧", "edge", "部署", "deploy"),
    "模型工具": ("模型服务", "sdk", "开发工具", "serving", "api", "工具链", "模型"),
}
CONFIDENCE_VALUE = {"high": 0.9, "medium": 0.65, "low": 0.4}
MAX_MODEL_DOCS = 11


class PipelineLLMError(ToolError):
    pass


class AgentPipeline:
    """Explicit state-machine implementation of the retrieval and evidence loop."""

    def __init__(
        self,
        *,
        settings: Settings,
        repo: Repository,
        search_tool: SearchTool,
        reader: PageReader,
        llm: LLMClient,
        cancel_event: threading.Event | None = None,
        on_state=None,
        now: datetime | None = None,
        delay_seconds: float | None = None,
    ):
        self.settings = settings
        self.repo = repo
        self.search_tool = search_tool
        self.reader = reader
        self.llm = llm
        self.cancel_event = cancel_event or threading.Event()
        self.on_state = on_state
        self.now = now or datetime.now(settings.tz)
        self.delay = settings.demo_step_delay_seconds if delay_seconds is None else delay_seconds
        self.state: dict[str, Any] = {}
        self.budget: BudgetController | None = None
        self._finalized = False
        self._finalizing = False
        self._facts_seen: dict[str, bool] = {}
        self._evidence_seen: dict[tuple[str, str], bool] = {}
        self._rejected_out_of_window = 0
        self._rejected_without_evidence = 0
        self._raw_out_of_window_events = 0
        self._budget_notice: BudgetError | None = None
        self._search_success = 0
        self._search_failures = 0
        self._read_success = 0
        self._read_failures = 0
        self._gap_rounds_used = 0
        self._omitted_events = 0

    # ---------- public entrypoint ----------

    def run(self, state: dict) -> dict:
        self.state = state
        state["status"] = "running"
        state["started_at"] = iso_now()
        set_stage(state, "planning", "正在规划检索策略", 8)
        self.budget = BudgetController(self.repo, state, self.settings)
        self._save()
        try:
            self.budget.ensure_capacity()
            self._check_stop()
            self._plan()
            self._check_stop()
            self._initial_search()
            self._check_stop()
            self._initial_read()
            self._check_stop()
            if self._read_success:
                self._extract_round(0)
            self._check_stop()
            self._discover_gaps()
            self._topup_loop()
            self._check_stop()
            status, reason, message = self._decide_completion()
            self._finalize(status, reason, message)
        except CancelledError:
            self._finalize(
                "cancelled",
                "user_cancel",
                "任务已取消，已完成的检索与事件结果已保留。",
            )
        except TimeBudgetExceeded as exc:
            self._finalize(
                "partial",
                "timeout",
                f"已达到时间上限，任务停止。{exc.message}",
            )
        except DailyBudgetExceeded as exc:
            self._finalize(
                "partial",
                "daily_budget_exhausted",
                f"今日额度已用完，任务提前停止。{exc.message}",
            )
        except RunBudgetExceeded as exc:
            self._finalize(
                "partial",
                "run_budget_exhausted",
                f"达到本次任务预算上限，任务提前停止。{exc.message}",
            )
        except BudgetError as exc:
            self._finalize("partial", "budget_exhausted", exc.message)
        except ToolError as exc:
            add_warning(self.state, exc.message)
            has_events = bool(self.state.get("events"))
            self._finalize(
                "partial" if has_events else "failed",
                "service_unavailable",
                f"工具调用失败，任务停止：{exc.message}",
            )
        except Exception:
            logger.exception("Pipeline crashed for run %s", self.state.get("id"))
            add_warning(self.state, "任务执行出现内部异常，已保留可得的部分结果。")
            has_events = bool(self.state.get("events"))
            self._finalize(
                "partial" if has_events else "failed",
                "internal_error",
                "任务执行出现内部异常，已保留可得的部分结果。" if has_events else "任务执行失败。",
            )
        finally:
            if not self._finalized:
                try:
                    self._finalize(
                        "failed", "internal_error", "任务未能正常完成，请查看运行记录。"
                    )
                except Exception:
                    logger.exception("Final fallback failed for run %s", self.state.get("id"))
            try:
                self.budget.snapshot()
            except Exception:
                pass
        return self.state

    # ---------- persistence / stop helpers ----------

    def _save(self) -> None:
        if not self.state:
            return
        try:
            self.repo.save_state(self.state)
            if self.on_state:
                self.on_state(self.state)
        except Exception:
            logger.exception("Failed to persist state for run %s", self.state.get("id"))

    def _check_stop(self) -> None:
        if self.cancel_event.is_set() or self.state.get("cancel_requested"):
            self.state["cancel_requested"] = True
            raise CancelledError()
        if self.budget and self.budget.remaining_seconds() <= 0.2:
            raise TimeBudgetExceeded("本次任务已达到时间上限。", scope="time")

    def _sleep(self, seconds: float | None = None) -> None:
        duration = self.delay if seconds is None else seconds
        if duration <= 0:
            return
        if self.budget:
            duration = min(duration, max(0.0, self.budget.remaining_seconds() - 1))
        if duration <= 0:
            raise TimeBudgetExceeded("本次任务已达到时间上限。", scope="time")
        time.sleep(duration)
        self._check_stop()

    def _set_budget_notice(self, exc: BudgetError) -> None:
        if not isinstance(exc, TimeBudgetExceeded):
            self._budget_notice = exc
        add_warning(self.state, exc.message)

    # ---------- LLM wrapper ----------

    def _call_llm(self, method_name: str, context: dict) -> dict:
        assert self.budget is not None
        method = getattr(self.llm, method_name)
        last_error: ToolError | None = None
        for attempt in range(2):
            self._check_stop()
            self.budget.acquire("model")
            try:
                data, tokens = method(context)
                self.budget.record_model_tokens(
                    int(tokens.get("tokens_in", 0)), int(tokens.get("tokens_out", 0))
                )
                return data
            except BudgetError:
                raise
            except ToolError as exc:
                self.budget.record_model_tokens(0, 0)
                last_error = exc
                if self.state.get("mode") != "demo":
                    add_warning(self.state, f"模型调用失败：{exc.message}")
                if exc.code in {
                    "llm_auth",
                    "config_missing",
                    "llm_json_mode_unsupported",
                    "llm_bad_request",
                }:
                    break
                if self.budget.remaining_seconds() < 4:
                    break
                if attempt == 0:
                    self._sleep(min(0.35, self.delay + 0.15))
        assert last_error is not None
        raise last_error

    # ---------- query planning ----------

    def _plan(self) -> None:
        assert self.budget is not None
        set_stage(self.state, "planning", "正在生成中英文查询计划", 9)
        self._save()
        context = {
            "now": self.now.isoformat(timespec="minutes"),
            "timezone": self.settings.timezone,
            "days": 1 if self.state["window"] == "day" else 7,
            "topics": self.state["topics"],
            "focus_keywords": self.state.get("focus_keywords", []),
            "limit": self.settings.initial_query_limit,
        }
        plan = None
        try:
            plan = self._call_llm("plan_queries", context)
        except BudgetError:
            raise
        except ToolError as exc:
            # Authentication / incompatible JSON mode are configuration errors:
            # fail before spending search and read budget, and never fall back to
            # a misleading demo path.
            if exc.code in {
                "llm_auth",
                "config_missing",
                "llm_json_mode_unsupported",
                "llm_bad_request",
            }:
                raise
            add_warning(self.state, f"查询规划失败，改用规则化查询计划：{exc.message}")
        raw_queries = (plan or {}).get("queries", []) if plan else []
        normalized: list[dict] = []
        seen: set[str] = set()
        for item in raw_queries:
            if not isinstance(item, dict):
                continue
            text = normalize_ws(item.get("text", ""))
            purpose = normalize_ws(item.get("purpose", ""))
            if len(text) < 2 or not purpose or text.casefold() in seen:
                continue
            seen.add(text.casefold())
            topic = self._topic_for(item.get("topic", ""), text)
            normalized.append(
                {
                    "text": text[:220],
                    "purpose": purpose[:220],
                    "strategy": item.get("strategy")
                    if item.get("strategy") in {"open", "official", "specific"}
                    else "open",
                    "topic": topic,
                    "language": item.get("language")
                    if item.get("language") in {"zh", "en", "mixed"}
                    else "mixed",
                    "domains": list(item.get("domains") or [])[:3],
                }
            )
            if len(normalized) >= self.settings.initial_query_limit:
                break

        # Guarantee every selected topic gets at least one query.
        for topic in self.state["topics"]:
            if any(q["topic"] == topic for q in normalized):
                continue
            fallback = self._fallback_topic_queries(topic)
            if not fallback:
                continue
            candidate = fallback[0]
            if len(normalized) >= self.settings.initial_query_limit:
                normalized.pop()
            normalized.append(candidate)
            if not plan:
                break

        if not normalized:
            for topic in self.state["topics"]:
                for item in self._fallback_topic_queries(topic):
                    normalized.append(item)
                    if len(normalized) >= self.settings.initial_query_limit:
                        break
                if len(normalized) >= self.settings.initial_query_limit:
                    break
        if not normalized:
            raise PipelineLLMError("无法生成有效查询", code="plan_empty")

        normalized = normalized[: self.settings.initial_query_limit]
        queries = []
        for index, item in enumerate(normalized, start=1):
            queries.append(
                {
                    "id": f"q{index}",
                    **item,
                    "round": 0,
                    "gap_id": None,
                    "status": "planned",
                    "attempts": 0,
                    "result_count": 0,
                    "new_documents": 0,
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                }
            )
        self.state["queries"] = queries
        self.state["plan_notes"] = normalize_ws((plan or {}).get("notes", ""))[:500] or (
            "已按话题覆盖与中英文来源平衡生成初始查询。"
        )
        self._save()

    def _fallback_topic_queries(self, topic: str) -> list[dict]:
        key = self._preset_key(topic)
        if key == "agent":
            raw = [
                (
                    "Agent 框架 工具调用 权限 编排 最新发布",
                    "发现 Agent 框架近期在工具调用、权限与编排方面的变化",
                    "open",
                    "zh",
                ),
                (
                    "AI agent framework tool calling release notes official",
                    "寻找项目官方发布说明与版本变化",
                    "official",
                    "en",
                ),
            ]
        elif key == "inference":
            raw = [
                (
                    "推理引擎 量化 KV Cache 端侧 最新发布",
                    "发现推理引擎、量化与端侧部署的近期更新",
                    "open",
                    "zh",
                ),
                (
                    "inference engine quantization edge deployment release notes",
                    "寻找推理引擎官方版本说明与兼容性细节",
                    "official",
                    "en",
                ),
            ]
        elif key == "model_tools":
            raw = [
                (
                    "模型服务 SDK 开发者工具 最新更新",
                    "发现模型服务与开发工具链的近期变化",
                    "open",
                    "zh",
                ),
                (
                    "model serving SDK developer tools release notes changelog",
                    "寻找模型工具官方 release notes 与 SDK 变更",
                    "official",
                    "en",
                ),
            ]
        else:
            raw = [
                (
                    f"{topic} 最新发布 更新",
                    f"发现“{topic}”近期的重要技术变化",
                    "open",
                    "zh",
                ),
                (
                    f"{topic} release notes changelog official",
                    f"寻找“{topic}”的原始发布或官方变更说明",
                    "official",
                    "en",
                ),
            ]
        return [
            {
                "text": text,
                "purpose": purpose,
                "strategy": strategy,
                "topic": topic,
                "language": language,
                "domains": [],
            }
            for text, purpose, strategy, language in raw
        ]

    def _preset_key(self, topic: str) -> str | None:
        normalized = topic.casefold()
        for preset in TOPIC_PRESETS:
            if normalized == preset["label"].casefold():
                return preset["id"]
        if "agent" in normalized or "智能体" in normalized:
            return "agent"
        if any(word in normalized for word in ("推理", "inference", "量化")):
            return "inference"
        if any(word in normalized for word in ("sdk", "模型服务", "开发工具")):
            return "model_tools"
        return None

    def _topic_for(self, raw: str, text: str = "") -> str:
        topics = self.state["topics"]
        raw_norm = normalize_ws(raw).casefold()
        for topic in topics:
            if raw_norm == topic.casefold():
                return topic
        for topic in topics:
            if topic.casefold() in raw_norm or raw_norm in topic.casefold():
                return topic
        haystack = f"{raw_norm} {normalize_ws(text).casefold()}"
        for preset in TOPIC_PRESETS:
            if preset["label"] not in topics:
                continue
            if any(word.casefold() in haystack for word in TOPIC_KEYWORDS.get(preset["label"], ())):
                return preset["label"]
        if len(topics) == 1:
            return topics[0]
        return topics[0]

    # ---------- search ----------

    def _initial_search(self) -> None:
        set_stage(self.state, "searching", "正在执行初始搜索", 22)
        self._save()
        query_ids = [q["id"] for q in self.state["queries"] if q["round"] == 0]
        self._execute_queries(query_ids, 0)
        if self._search_success == 0 and self._search_failures > 0:
            raise ToolError("搜索服务连续失败，未能获得候选资料", code="search_unavailable")
        if not self.state["documents"]:
            add_warning(self.state, "搜索没有返回候选网页。")
        self._save()

    def _execute_queries(self, query_ids: list[str], round_no: int) -> dict:
        assert self.budget is not None
        qmap = {q["id"]: q for q in self.state["queries"]}
        ok = failed = 0
        for query_id in query_ids:
            self._check_stop()
            query = qmap.get(query_id)
            if not query:
                continue
            query["status"] = "running"
            query["started_at"] = iso_now()
            self._save()
            spec = QuerySpec(
                text=query["text"],
                purpose=query["purpose"],
                strategy=query.get("strategy", "open"),
                topic=query["topic"],
                language=query.get("language", "mixed"),
                domains=query.get("domains", []),
                round=round_no,
                gap_id=query.get("gap_id"),
            )
            hits = None
            last_error: ToolError | None = None
            for attempt in range(2):
                self._check_stop()
                try:
                    self.budget.acquire("search")
                except BudgetError as exc:
                    query["status"] = "skipped"
                    query["error"] = exc.message
                    query["finished_at"] = iso_now()
                    self._set_budget_notice(exc)
                    self._save()
                    return {"ok": ok, "failed": failed, "budget": True}
                query["attempts"] = int(query.get("attempts", 0)) + 1
                try:
                    hits = self.search_tool.search(
                        spec,
                        window=self.state["window"],
                        limit=self.settings.search_results_per_query,
                    )
                    break
                except ToolError as exc:
                    last_error = exc
                    if exc.transient and attempt == 0 and self.budget.remaining_seconds() > 4:
                        self._sleep(0.25)
                        continue
                    break
            if hits is None:
                query["status"] = "error"
                query["error"] = last_error.message if last_error else "搜索失败"
                query["finished_at"] = iso_now()
                self._search_failures += 1
                failed += 1
                add_warning(self.state, f"搜索失败：{query['error']}")
                self._save()
                continue
            query["status"] = "ok"
            query["error"] = None
            query["result_count"] = len(hits)
            new_docs = self._add_hits(query, hits)
            query["new_documents"] = new_docs
            query["finished_at"] = iso_now()
            self._search_success += 1
            ok += 1
            self.state["progress"] = {
                "percent": min(40, 22 + 3 * (ok + failed)),
                "stage": "searching",
                "message": f"已执行 {ok + failed} 条查询，获得 {len(self.state['documents'])} 个候选网页",
            }
            self._save()
            self._sleep()
        return {"ok": ok, "failed": failed, "budget": False}

    def _add_hits(self, query: dict, hits: list) -> int:
        existing = {doc.get("canonical_url") for doc in self.state["documents"]}
        added = 0
        blocked = 0
        for hit in hits:
            ok, _reason = quick_url_check(hit.url)
            if not ok:
                blocked += 1
                continue
            canonical = canonical_url(hit.url)
            if canonical in existing:
                continue
            existing.add(canonical)
            doc = {
                "id": f"d{len(self.state['documents']) + 1}",
                "url": hit.url,
                "canonical_url": canonical,
                "domain": (hit.domain or display_domain(hit.url)).lower(),
                "title": normalize_ws(hit.title)[:240],
                "snippet": normalize_ws(hit.snippet)[:900],
                "published_at": hit.published_date,
                "search_score": hit.score,
                "query_ids": [query["id"]],
                "topic": query["topic"],
                "read_status": "pending",
                "read_error": None,
                "fetched_at": None,
                "content": "",
                "content_excerpt": "",
                "content_hash": None,
                "duplicate_of": None,
            }
            self.state["documents"].append(doc)
            added += 1
        if blocked:
            add_warning(self.state, "已跳过搜索结果中的本机/内网或非法链接。")
        return added

    # ---------- page reading ----------

    def _initial_read(self) -> None:
        set_stage(self.state, "reading", "正在筛选并读取正文", 44)
        self._save()
        targets = self._select_read_targets(self.settings.initial_read_limit)
        if not targets:
            add_warning(self.state, "没有可读取的候选网页。")
        self._read_targets(targets)
        if self._read_failures:
            add_warning(
                self.state,
                f"有 {self._read_failures} 个来源正文读取失败，失败页面未作为证据使用。",
            )

    def _select_read_targets(
        self, limit: int, candidate_ids: set[str] | None = None
    ) -> list[dict]:
        if self.budget:
            remaining = int(self.state["budget"]["limits"]["reads"]) - int(
                self.state["usage"]["read_attempts"]
            )
            limit = min(limit, remaining)
        if limit <= 0:
            return []
        queries = {q["id"]: q for q in self.state["queries"]}
        docs = [
            d
            for d in self.state["documents"]
            if d.get("read_status") == "pending"
            and (candidate_ids is None or d["id"] in candidate_ids)
            and quick_url_check(d["url"])[0]
        ]
        groups: dict[str, list[dict]] = {topic: [] for topic in self.state["topics"]}
        for doc in docs:
            groups.setdefault(doc.get("topic", self.state["topics"][0]), []).append(doc)
        for topic_docs in groups.values():
            topic_docs.sort(key=lambda d: document_priority(d, queries), reverse=True)
        selected: list[dict] = []
        domain_count: dict[str, int] = {}
        cursor = 0
        while len(selected) < limit:
            progressed = False
            for topic in self.state["topics"]:
                topic_docs = groups.get(topic, [])
                while cursor < len(topic_docs):
                    doc = topic_docs[cursor]
                    cursor += 1
                    if doc in selected:
                        continue
                    domain = doc.get("domain", "")
                    if domain_count.get(domain, 0) >= 2:
                        continue
                    selected.append(doc)
                    domain_count[domain] = domain_count.get(domain, 0) + 1
                    progressed = True
                    break
                if len(selected) >= limit:
                    break
            if not progressed:
                break
            cursor = 0
            groups = {
                topic: [d for d in items if d not in selected] for topic, items in groups.items()
            }
        return selected

    def _read_targets(self, targets: list[dict]) -> int:
        assert self.budget is not None
        successes = 0
        for index, doc in enumerate(targets, start=1):
            self._check_stop()
            try:
                self.budget.acquire("read")
            except BudgetError as exc:
                doc["read_status"] = "skipped"
                doc["read_error"] = exc.message
                self._set_budget_notice(exc)
                self._save()
                break
            doc["read_status"] = "reading"
            doc["fetched_at"] = iso_now()
            self.state["progress"] = {
                "percent": min(60, 45 + index),
                "stage": "reading",
                "message": f"正在读取第 {index}/{len(targets)} 篇正文",
            }
            self._save()
            timeout = min(
                self.settings.page_timeout_seconds,
                max(3.0, self.budget.remaining_seconds() - 4),
            )
            result = self.reader.read(doc["url"], timeout_seconds=timeout)
            self._sleep()
            if result.ok:
                doc["read_status"] = "success"
                doc["url"] = result.final_url or doc["url"]
                doc["canonical_url"] = canonical_url(doc["url"])
                doc["domain"] = display_domain(doc["url"])
                doc["title"] = normalize_ws(result.title or doc["title"])[:300]
                doc["published_at"] = result.published_at or doc.get("published_at")
                doc["content"] = result.content
                doc["content_excerpt"] = result.content[:1200]
                doc["content_hash"] = content_hash(result.content)
                doc["read_error"] = None
                doc["language"] = result.language
                previous = [
                    other
                    for other in self.state["documents"]
                    if other["id"] != doc["id"]
                    and other.get("read_status") == "success"
                    and other.get("content")
                ]
                duplicate_of = is_near_duplicate(doc, previous)
                doc["duplicate_of"] = duplicate_of
                self._read_success += 1
                successes += 1
            else:
                doc["read_status"] = "failed"
                doc["read_error"] = result.error or "正文读取失败"
                self._read_failures += 1
            self._save()
        return successes

    # ---------- extraction ----------

    def _extract_round(self, round_no: int) -> dict:
        set_stage(
            self.state,
            "extracting" if round_no == 0 else "gap_reading",
            "正在聚合事件并核验逐字证据",
            64 if round_no == 0 else 88,
        )
        self._save()
        extracted_ids = set(self.state.get("_extracted_doc_ids", []))
        all_read = [
            d
            for d in self.state["documents"]
            if d.get("read_status") == "success" and d.get("content")
        ]
        candidates = [d for d in all_read if d["id"] not in extracted_ids and not d.get("duplicate_of")]
        if not candidates:
            return {"new_events": 0, "new_facts": 0, "extracted_docs": 0}
        candidates.sort(key=lambda d: (d.get("duplicate_of") is None, d.get("published_at") or ""), reverse=True)
        selected: list[dict] = []
        per_topic: dict[str, int] = {}
        for doc in candidates:
            if len(selected) >= MAX_MODEL_DOCS:
                break
            topic = doc.get("topic", "")
            if per_topic.get(topic, 0) >= 4 and len(candidates) > MAX_MODEL_DOCS:
                continue
            selected.append(doc)
            per_topic[topic] = per_topic.get(topic, 0) + 1
        if not selected:
            return {"new_events": 0, "new_facts": 0, "extracted_docs": 0}

        context = {
            "now": self.now.isoformat(timespec="minutes"),
            "timezone": self.settings.timezone,
            "days": 1 if self.state["window"] == "day" else 7,
            "topics": self.state["topics"],
            "round": round_no,
            "existing_events": [
                {
                    "event_key": e["event_key"],
                    "title": e["title"],
                    "topic": e["topic"],
                    "date": e.get("event_date"),
                    "facts": [f["statement"] for f in e.get("facts", [])],
                }
                for e in self.state.get("events", [])
            ],
            "documents": [
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "domain": doc["domain"],
                    "url": doc["url"],
                    "published_at": doc.get("published_at"),
                    "content": doc["content"],
                }
                for doc in selected
            ],
        }
        before_events = len(self.state.get("events", []))
        before_facts = sum(len(e.get("facts", [])) for e in self.state.get("events", []))
        try:
            data = self._call_llm("extract_events", context)
        except BudgetError:
            raise
        except ToolError as exc:
            add_warning(self.state, f"事件抽取失败：{exc.message}")
            raise PipelineLLMError(
                f"未能从正文生成可核验事件：{exc.message}", code="extraction_failed"
            ) from exc
        raw_events = data.get("events", []) if isinstance(data, dict) else []
        docs_by_id = {doc["id"]: doc for doc in all_read}
        self._process_events(raw_events, docs_by_id)
        self.state["_extracted_doc_ids"] = sorted(
            set(self.state.get("_extracted_doc_ids", [])) | {doc["id"] for doc in selected}
        )
        self._save()
        return {
            "new_events": max(0, len(self.state.get("events", [])) - before_events),
            "new_facts": max(
                0,
                sum(len(e.get("facts", [])) for e in self.state.get("events", [])) - before_facts,
            ),
            "extracted_docs": len(selected),
        }

    def _process_events(self, raw_events: list[dict], docs_by_id: dict[str, dict]) -> None:
        from ..pipeline.evidence import event_score

        new_events = 0
        for raw in raw_events:
            if not isinstance(raw, dict):
                continue
            topic = self._topic_for(raw.get("topic", ""), raw.get("title", ""))
            if topic not in self.state["topics"]:
                continue
            parsed_date = parse_event_date(raw.get("event_date"), self.now)
            if raw.get("event_date") and parsed_date is None:
                date_confidence = "unknown"
            else:
                date_confidence = raw.get("date_confidence", "unknown")
            if parsed_date is None:
                date_confidence = "unknown"
            if parsed_date and event_too_old(
                parsed_date,
                self._window_start(),
                self._window_end(),
            ):
                self._raw_out_of_window_events += 1
                continue

            facts = []
            evidence_docs: dict[str, dict] = {}
            unsupported = 0
            for raw_fact in raw.get("facts", []):
                verified_evidence = []
                for ev in raw_fact.get("evidence", []):
                    doc_id = ev.get("document_id", "")
                    quote = normalize_ws(ev.get("quote", ""))
                    doc = docs_by_id.get(doc_id)
                    verified = bool(doc and quote_verified(quote, doc.get("content", "")))
                    key = (doc_id, quote)
                    prior = self._evidence_seen.get(key)
                    self._evidence_seen[key] = bool(prior or verified)
                    if not verified or not doc:
                        continue
                    item = {
                        "document_id": doc_id,
                        "quote": quote,
                        "verified": True,
                        "verification_note": "与已读取正文逐字匹配（仅归一化空白/全半角）",
                        "url": doc["url"],
                        "title": doc["title"],
                        "domain": doc["domain"],
                        "published_at": doc.get("published_at"),
                    }
                    verified_evidence.append(item)
                    evidence_docs[doc_id] = doc
                statement = normalize_ws(raw_fact.get("statement", ""))[:500]
                conditions = normalize_ws(raw_fact.get("conditions", ""))[:300]
                fact_key = re.sub(
                    r"[^a-z0-9\u4e00-\u9fff]+", "", f"{statement}{conditions}".lower()
                )
                supported = bool(verified_evidence) and len(statement) >= 2
                self._facts_seen[fact_key] = bool(self._facts_seen.get(fact_key) or supported)
                if not supported:
                    unsupported += 1
                    continue
                facts.append(
                    {
                        "statement": statement,
                        "category": raw_fact.get("category", "other"),
                        "conditions": conditions,
                        "status": "supported",
                        "evidence": verified_evidence,
                    }
                )
            unresolved = list(raw.get("unresolved", []))
            if unsupported:
                unresolved.append(f"有 {unsupported} 条模型陈述未能通过原文片段核验，已排除。")
                self._rejected_without_evidence += unsupported
            if not facts:
                continue
            primary_id = raw.get("primary_document_id", "")
            if primary_id not in docs_by_id:
                primary_id = facts[0]["evidence"][0]["document_id"]
            if primary_id not in evidence_docs:
                evidence_docs[primary_id] = docs_by_id[primary_id]
            resolved_unresolved = list(raw.get("resolved_unresolved", []))
            if not parsed_date and not any("日期" in item for item in unresolved):
                unresolved.append("事件日期尚未确认，未使用文章发布日期代替。")
            sources = []
            for doc_id, doc in evidence_docs.items():
                sources.append(
                    {
                        "document_id": doc_id,
                        "title": doc["title"],
                        "url": doc["url"],
                        "domain": doc["domain"],
                        "published_at": doc.get("published_at"),
                        "fetched_at": doc.get("fetched_at"),
                        "role": "primary" if doc_id == primary_id else "supporting",
                    }
                )
            sources.sort(key=lambda item: item["role"] != "primary")
            domains = sorted({s["domain"] for s in sources if s["domain"]})
            candidate = {
                "event_key": normalize_key(raw.get("event_key", ""))
                or normalize_key(f"{raw.get('project','')}-{raw.get('title','')}"),
                "title": normalize_ws(raw.get("title", ""))[:180],
                "project": normalize_ws(raw.get("project", ""))[:100],
                "topic": topic,
                "event_type": raw.get("event_type", "other"),
                "event_date": parsed_date.isoformat() if parsed_date else None,
                "date_confidence": date_confidence,
                "summary": normalize_ws(raw.get("summary", ""))[:700],
                "why_it_matters": normalize_ws(raw.get("why_it_matters", ""))[:500],
                "confidence": raw.get("confidence", "medium"),
                "confidence_score": CONFIDENCE_VALUE.get(raw.get("confidence", "medium"), 0.65),
                "facts": facts,
                "unresolved": unresolved[:10],
                "resolved_unresolved": resolved_unresolved,
                "primary_document_id": primary_id,
                "sources": sources,
                "source_count": len(sources),
                "independent_source_count": len(domains),
                "source_domains": domains,
                "date_conflict": False,
            }
            matched = None
            for existing in self.state.get("events", []):
                if same_event(existing, candidate):
                    matched = existing
                    break
            if matched:
                merge_event(matched, candidate)
                matched["confidence_score"] = event_score(
                    matched, self.now, self.state["window"]
                )
            else:
                candidate["confidence_score"] = event_score(
                    candidate, self.now, self.state["window"]
                )
                self.state.setdefault("events", []).append(candidate)
                new_events += 1
        if self._raw_out_of_window_events:
            add_warning(
                self.state,
                f"已过滤 {self._raw_out_of_window_events} 个事件日期不在所选时间窗内的候选事件。",
            )
        if new_events:
            add_warning(
                self.state,
                "来源数与域名去重数不等于独立验证；事实仅通过原文片段匹配检查。",
            )

    # ---------- gaps / adaptive search ----------

    def _discover_gaps(self) -> None:
        assert self.budget is not None
        set_stage(self.state, "checking_gaps", "检查日期、条件、冲突与覆盖缺口", 72)
        self._save()
        self.state.setdefault("gaps", [])
        existing_signatures = {
            (g.get("reason_code"), g.get("topic"), g.get("event_key"))
            for g in self.state["gaps"]
        }
        for topic in self.state["topics"]:
            if not any(e.get("topic") == topic for e in self.state.get("events", [])):
                self._append_gap(
                    reason_code="topic_uncovered",
                    description=f"话题“{topic}”尚未形成有逐字证据支持的事件。",
                    topic=topic,
                    priority="high",
                    event_key=None,
                    query=self._fallback_topic_queries(topic)[0] if self._fallback_topic_queries(topic) else None,
                )
        for event in self.state.get("events", []):
            if not event.get("event_date"):
                self._append_gap(
                    reason_code="ambiguous_date",
                    description=f"“{event['title']}”的事件日期尚不明确。",
                    topic=event["topic"],
                    priority="medium",
                    event_key=event["event_key"],
                    query=self._gap_query(event, "ambiguous_date"),
                )
            if any(fact_has_missing_conditions(f) for f in event.get("facts", [])):
                self._append_gap(
                    reason_code="missing_conditions",
                    description=f"“{event['title']}”的性能结论缺少硬件、基线或负载条件。",
                    topic=event["topic"],
                    priority="high",
                    event_key=event["event_key"],
                    query=self._gap_query(event, "missing_conditions"),
                )
            if event.get("date_conflict") or contains_conflict(event.get("unresolved", [])):
                self._append_gap(
                    reason_code="conflict",
                    description=f"“{event['title']}”存在来源结论冲突或未决的兼容性差异。",
                    topic=event["topic"],
                    priority="high",
                    event_key=event["event_key"],
                    query=self._gap_query(event, "conflict"),
                )

        if self.state.get("events"):
            try:
                gap_context = {
                    "topics": self.state["topics"],
                    "days": 1 if self.state["window"] == "day" else 7,
                    "round": 0,
                    "max_rounds": self.settings.max_gap_rounds,
                    "remaining": {
                        "searches": self.state["budget"]["limits"]["searches"]
                        - self.state["usage"]["search_calls"],
                        "reads": self.state["budget"]["limits"]["reads"]
                        - self.state["usage"]["read_attempts"],
                        "model_calls": self.state["budget"]["limits"]["model_calls"]
                        - self.state["usage"]["model_calls"],
                    },
                    "queries_tried": [q["text"] for q in self.state["queries"]],
                    "events": self.state.get("events", []),
                    "existing_gaps": [
                        {"reason_code": g["reason_code"], "description": g["description"]}
                        for g in self.state["gaps"]
                    ],
                    "read_failures": [
                        {"url": d["url"], "error": d.get("read_error")}
                        for d in self.state["documents"]
                        if d.get("read_status") == "failed"
                    ],
                }
                data = self._call_llm("analyze_gaps", gap_context)
                self._merge_llm_gaps(data.get("gaps", []))
            except BudgetError as exc:
                self._set_budget_notice(exc)
            except ToolError as exc:
                add_warning(self.state, f"缺口分析模型调用失败，保留规则化缺口：{exc.message}")

        self._dedupe_gaps()
        self.state["gaps"] = self.state["gaps"][:8]
        self._save()

    def _append_gap(
        self,
        *,
        reason_code: str,
        description: str,
        topic: str,
        priority: str,
        event_key: str | None,
        query: dict | None,
    ) -> dict:
        gap = {
            "id": f"g{len(self.state.get('gaps', [])) + 1}",
            "reason_code": reason_code,
            "description": normalize_ws(description)[:300],
            "topic": topic,
            "priority": priority,
            "status": "open",
            "event_key": event_key,
            "query": query,
            "queries_tried": [],
            "created_round": 0,
            "resolved_round": None,
            "resolution_note": None,
        }
        self.state.setdefault("gaps", []).append(gap)
        return gap

    def _gap_query(self, event: dict, reason_code: str) -> dict:
        project = event.get("project") or event.get("title", "")
        if reason_code == "ambiguous_date":
            text = f"{project} 发布日期 官方公告"
            purpose = "确认事件的实际发布日期，区分文章发布时间"
        elif reason_code == "missing_conditions":
            text = f"{project} 性能 测试 硬件 基线 负载 条件"
            purpose = "补齐性能结论的硬件、基线或负载条件"
        elif reason_code == "conflict":
            text = f"{project} 兼容性 官方说明 文档"
            purpose = "寻找原始文档，解决来源之间的兼容性冲突"
        else:
            text = f"{project} official release notes"
            purpose = "寻找原始发布或官方说明"
        return {
            "text": text[:220],
            "purpose": purpose,
            "strategy": "official",
            "domains": [],
        }

    def _merge_llm_gaps(self, llm_gaps: list[dict]) -> None:
        tried = {normalize_ws(q["text"]).casefold() for q in self.state["queries"]}
        for item in llm_gaps[:4]:
            reason = item.get("reason_code", "other")
            allowed = {
                "missing_primary",
                "ambiguous_date",
                "missing_conditions",
                "conflict",
                "topic_uncovered",
                "other",
            }
            if reason not in allowed:
                reason = "other"
            topic = self._topic_for(item.get("topic", ""), item.get("description", ""))
            description = normalize_ws(item.get("description", ""))[:300]
            if not description:
                continue
            query = item.get("query")
            if isinstance(query, dict) and normalize_ws(query.get("text", "")).casefold() in tried:
                query = None
            if isinstance(query, dict):
                query = {
                    "text": normalize_ws(query.get("text", ""))[:220],
                    "purpose": normalize_ws(query.get("purpose", ""))[:220]
                    or "验证这个证据缺口",
                    "strategy": query.get("strategy", "specific")
                    if query.get("strategy") in {"open", "official", "specific"}
                    else "specific",
                    "domains": list(query.get("domains") or [])[:3],
                }
            existing = None
            for gap in self.state["gaps"]:
                if (
                    gap["reason_code"] == reason
                    and gap["topic"] == topic
                    and gap["status"] == "open"
                ):
                    existing = gap
                    break
            if existing:
                if query and not existing.get("query"):
                    existing["query"] = query
                if item.get("priority") == "high":
                    existing["priority"] = "high"
                continue
            events_in_topic = [e for e in self.state.get("events", []) if e.get("topic") == topic]
            event_key = events_in_topic[0]["event_key"] if len(events_in_topic) == 1 else None
            self._append_gap(
                reason_code=reason,
                description=description,
                topic=topic,
                priority=item.get("priority", "medium"),
                event_key=event_key,
                query=query,
            )

    def _dedupe_gaps(self) -> None:
        deduped = []
        seen = set()
        for gap in self.state.get("gaps", []):
            signature = (
                gap.get("reason_code"),
                gap.get("topic"),
                normalize_ws(gap.get("description", ""))[:80],
            )
            if signature in seen:
                continue
            seen.add(signature)
            gap["id"] = f"g{len(deduped) + 1}"
            deduped.append(gap)
        self.state["gaps"] = deduped

    def _topup_loop(self) -> None:
        assert self.budget is not None
        for round_no in range(1, self.settings.max_gap_rounds + 1):
            self._check_stop()
            if self._budget_notice:
                break
            actionable = [
                gap
                for gap in self.state.get("gaps", [])
                if gap.get("status") == "open"
                and gap.get("priority") in {"high", "medium"}
                and isinstance(gap.get("query"), dict)
                and len(gap["query"].get("text", "")) >= 2
            ]
            if not actionable:
                break
            selected = actionable[:2]
            new_queries = []
            for gap in selected:
                query_text = normalize_ws(gap["query"]["text"])
                if query_text.casefold() in {
                    normalize_ws(q["text"]).casefold() for q in self.state["queries"]
                }:
                    gap["status"] = "accepted"
                    gap["resolution_note"] = "该补搜查询已执行过，避免重复消耗额度。"
                    continue
                query_id = f"q{len(self.state['queries']) + 1}"
                query = {
                    "id": query_id,
                    "text": query_text,
                    "purpose": normalize_ws(gap["query"].get("purpose", "验证证据缺口")),
                    "strategy": gap["query"].get("strategy", "specific"),
                    "topic": gap["topic"],
                    "language": "mixed",
                    "domains": list(gap["query"].get("domains") or []),
                    "round": round_no,
                    "gap_id": gap["id"],
                    "status": "planned",
                    "attempts": 0,
                    "result_count": 0,
                    "new_documents": 0,
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                }
                self.state["queries"].append(query)
                new_queries.append(query)
                gap["status"] = "in_progress"
                gap["queries_tried"].append(query_text)
            if not new_queries:
                continue
            self._gap_rounds_used = round_no
            action = {
                "round": round_no,
                "reason": "；".join(g["description"] for g in selected)[:600],
                "gap_ids": [g["id"] for g in selected],
                "query_texts": [q["text"] for q in new_queries],
                "started_at": iso_now(),
                "finished_at": None,
                "new_events": 0,
                "new_facts": 0,
                "resolved_gaps": 0,
                "outcome": "running",
            }
            self.state.setdefault("actions", []).append(action)
            self.state["gaps"] = self.state["gaps"]
            set_stage(self.state, "gap_searching", f"第 {round_no} 轮定向补搜：{selected[0]['description']}", 78)
            self._save()

            doc_ids_before = {d["id"] for d in self.state["documents"]}
            result = self._execute_queries([q["id"] for q in new_queries], round_no)
            new_doc_ids = {
                d["id"] for d in self.state["documents"] if d["id"] not in doc_ids_before
            }
            if result.get("budget"):
                self._finish_action(action, 0, 0, 0, "budget_stopped")
                self._mark_selected_gaps(selected, "unresolved", "搜索额度不足，补搜未执行。")
                self._save()
                break
            targets = self._select_read_targets(4, candidate_ids=new_doc_ids)
            set_stage(self.state, "gap_reading", f"读取第 {round_no} 轮补搜资料", 82)
            self._save()
            successes = self._read_targets(targets)
            before_events = set(e["event_key"] for e in self.state.get("events", []))
            before_fact_keys = {
                (e["event_key"], re.sub(r"\W+", "", f.get("statement", "")))
                for e in self.state.get("events", [])
                for f in e.get("facts", [])
            }
            extraction_error = None
            if successes:
                try:
                    self._extract_round(round_no)
                except BudgetError:
                    raise
                except ToolError as exc:
                    extraction_error = exc.message
                    add_warning(self.state, f"补搜资料未能形成新证据：{exc.message}")
            after_events = self.state.get("events", [])
            new_event_count = sum(1 for e in after_events if e["event_key"] not in before_events)
            after_fact_keys = {
                (e["event_key"], re.sub(r"\W+", "", f.get("statement", "")))
                for e in after_events
                for f in e.get("facts", [])
            }
            new_fact_count = len(after_fact_keys - before_fact_keys)
            resolved = 0
            for gap in selected:
                resolved_flag = self._resolve_gap(
                    gap, round_no, new_fact_count, successes, extraction_error
                )
                if resolved_flag:
                    resolved += 1
            action_new_events = new_event_count
            action_new_facts = new_fact_count
            if resolved or new_event_count or new_fact_count:
                outcome = "helpful"
            elif extraction_error:
                outcome = "failed"
            else:
                outcome = "no_new_value"
            self._finish_action(
                action, action_new_events, action_new_facts, resolved, outcome
            )
            for gap in selected:
                if gap["status"] in {"in_progress"}:
                    gap["status"] = "unresolved"
                    gap["resolution_note"] = "补搜未解决该缺口，保留为未确认事项。"
            self._save()
            if outcome == "no_new_value" or outcome == "failed":
                break
        for gap in self.state.get("gaps", []):
            if gap.get("status") == "in_progress":
                gap["status"] = "unresolved"
        self._save()

    def _finish_action(
        self, action: dict, new_events: int, new_facts: int, resolved: int, outcome: str
    ) -> None:
        action["finished_at"] = iso_now()
        action["new_events"] = new_events
        action["new_facts"] = new_facts
        action["resolved_gaps"] = resolved
        action["outcome"] = outcome

    def _mark_selected_gaps(self, gaps: list[dict], status: str, note: str) -> None:
        for gap in gaps:
            if gap.get("status") in {"in_progress", "open"}:
                gap["status"] = status
                gap["resolution_note"] = note

    def _resolve_gap(
        self,
        gap: dict,
        round_no: int,
        new_fact_count: int,
        read_successes: int,
        extraction_error: str | None,
    ) -> bool:
        if extraction_error or not read_successes:
            gap["status"] = "unresolved"
            gap["resolution_note"] = (
                "补搜没有获得可读正文。" if not read_successes else "补搜资料未能完成证据抽取。"
            )
            return False
        related = None
        for event in self.state.get("events", []):
            if gap.get("event_key") and event["event_key"] == gap["event_key"]:
                related = event
                break
        if related is None:
            candidates = [e for e in self.state.get("events", []) if e.get("topic") == gap["topic"]]
            if len(candidates) == 1:
                related = candidates[0]
        reason = gap["reason_code"]
        resolved = False
        note = ""
        if reason == "topic_uncovered":
            resolved = any(e.get("topic") == gap["topic"] for e in self.state.get("events", []))
            note = "补搜后该话题形成了有证据支持的事件。"
        elif reason == "ambiguous_date":
            resolved = bool(related and related.get("event_date"))
            note = "补搜补齐了事件日期。" if resolved else "补搜仍未确认事件日期。"
        elif reason == "missing_conditions":
            perf = [
                f
                for f in (related or {}).get("facts", [])
                if f.get("category") == "performance"
            ]
            resolved = bool(perf and all(normalize_ws(f.get("conditions")) for f in perf))
            note = "补搜补齐了性能结论的适用条件。" if resolved else "性能条件仍不完整。"
        elif reason == "conflict":
            resolved = bool(
                related
                and not related.get("date_conflict")
                and not contains_conflict(related.get("unresolved", []))
            )
            note = (
                "补充来源后冲突已解释或解除。"
                if resolved
                else "冲突尚未被原始资料解决，保留为未确认。"
            )
        else:
            resolved = new_fact_count > 0
            note = (
                "补搜补充了新的已核验事实。"
                if resolved
                else "补搜没有补充可核验事实。"
            )
        gap["status"] = "resolved" if resolved else "unresolved"
        gap["resolution_note"] = note
        if resolved:
            gap["resolved_round"] = round_no
        return resolved

    # ---------- completion ----------

    def _decide_completion(self) -> tuple[str, str, str]:
        events = self.state.get("events", [])
        open_gaps = [
            g
            for g in self.state.get("gaps", [])
            if g.get("status") in {"open", "in_progress", "unresolved"}
        ]
        high_gaps = [g for g in open_gaps if g.get("priority") == "high"]
        covered = {e["topic"] for e in events}
        missing_topics = [t for t in self.state["topics"] if t not in covered]
        if self._budget_notice:
            reason = (
                "daily_budget_exhausted"
                if self._budget_notice.scope == "daily"
                else "run_budget_exhausted"
            )
            return (
                "partial",
                reason,
                f"预算限制导致任务提前停止；已保留 {len(events)} 个事件。",
            )
        if not events:
            if self._search_success == 0:
                return "failed", "service_unavailable", "搜索服务未能返回候选资料，任务失败。"
            if not self.state.get("documents"):
                return "completed", "no_results", "所选时间窗内没有找到相关候选网页。"
            if self._read_success == 0:
                return (
                    "partial",
                    "read_failed",
                    "找到了候选网页，但没有来源可通过正文读取与证据核验。",
                )
            return (
                "completed",
                "no_verifiable_events",
                "读取了资料，但没有形成满足逐字证据要求的事件；未用搜索摘要代替正文。",
            )
        if high_gaps:
            if self._gap_rounds_used >= self.settings.max_gap_rounds:
                return (
                    "partial",
                    "gap_rounds_exhausted",
                    f"已生成 {len(events)} 个事件，但仍有 {len(high_gaps)} 个高价值缺口；补搜轮次已用完。",
                )
            return (
                "partial",
                "evidence_gaps_remaining",
                f"已生成 {len(events)} 个事件，但仍有 {len(high_gaps)} 个高价值缺口未解决。",
            )
        if missing_topics:
            return (
                "partial",
                "topic_uncovered",
                f"部分话题没有形成事件：{'、'.join(missing_topics)}。",
            )
        if open_gaps:
            return (
                "completed",
                "low_value_gaps",
                f"已覆盖全部话题；另有 {len(open_gaps)} 个低优先级缺口保留为未确认事项。",
            )
        return (
            "completed",
            "coverage_sufficient",
            f"主要方向已覆盖，{len(events)} 个事件的关键事实都有已读取正文中的逐字证据。",
        )

    def _finalize(self, status: str, reason: str, message: str) -> None:
        if self._finalized or self._finalizing:
            return
        self._finalizing = True
        try:
            set_stage(self.state, "verifying", "正在核验引用并保存结果", 94)
            self._save()
            from ..pipeline.evidence import event_score

            final_events = []
            for event in self.state.get("events", []):
                verified_facts = []
                for fact in event.get("facts", []):
                    verified_evidence = []
                    for evidence in fact.get("evidence", []):
                        doc = next(
                            (
                                d
                                for d in self.state.get("documents", [])
                                if d["id"] == evidence.get("document_id")
                            ),
                            None,
                        )
                        if doc and quote_verified(evidence.get("quote", ""), doc.get("content", "")):
                            evidence["verified"] = True
                            verified_evidence.append(evidence)
                    if verified_evidence:
                        fact["evidence"] = verified_evidence
                        fact["status"] = "supported"
                        verified_facts.append(fact)
                event["facts"] = verified_facts
                if not verified_facts:
                    continue
                # Rebuild sources from citations only.
                doc_ids = {
                    ev["document_id"]
                    for fact in verified_facts
                    for ev in fact.get("evidence", [])
                }
                source_map = {d["id"]: d for d in self.state.get("documents", [])}
                sources = []
                for doc_id in doc_ids:
                    doc = source_map.get(doc_id)
                    if not doc:
                        continue
                    sources.append(
                        {
                            "document_id": doc_id,
                            "title": doc["title"],
                            "url": doc["url"],
                            "domain": doc["domain"],
                            "published_at": doc.get("published_at"),
                            "fetched_at": doc.get("fetched_at"),
                            "role": "primary"
                            if doc_id == event.get("primary_document_id")
                            else "supporting",
                        }
                    )
                if not sources:
                    continue
                sources.sort(key=lambda s: s["role"] != "primary")
                event["sources"] = sources
                event["source_count"] = len(sources)
                event["source_domains"] = sorted({s["domain"] for s in sources if s["domain"]})
                event["independent_source_count"] = len(event["source_domains"])
                if not event.get("primary_document_id") and sources:
                    event["primary_document_id"] = sources[0]["document_id"]
                event["confidence_score"] = event_score(event, self.now, self.state["window"])
                final_events.append(event)
            deduped = []
            for event in sorted(
                final_events, key=lambda e: e.get("confidence_score", 0), reverse=True
            ):
                merged = None
                for existing in deduped:
                    if same_event(existing, event):
                        merged = existing
                        break
                if merged:
                    merge_event(merged, event)
                    merged["confidence_score"] = event_score(
                        merged, self.now, self.state["window"]
                    )
                else:
                    deduped.append(event)
            deduped.sort(key=lambda e: e.get("confidence_score", 0), reverse=True)
            if len(deduped) > self.settings.max_events:
                self._omitted_events = len(deduped) - self.settings.max_events
                add_warning(
                    self.state,
                    f"按证据完整度仅保留前 {self.settings.max_events} 个事件，未为填满页面扩充。",
                )
            self.state["events"] = deduped[: self.settings.max_events]
            self.state["omitted_event_count"] = self._omitted_events

            facts_total = len(self._facts_seen)
            facts_supported = sum(1 for value in self._facts_seen.values() if value)
            evidence_total = len(self._evidence_seen)
            evidence_verified = sum(1 for value in self._evidence_seen.values() if value)
            rate = (
                round(evidence_verified / evidence_total * 100, 1)
                if evidence_total
                else None
            )
            self.state["verification"] = {
                "facts_total": facts_total,
                "facts_supported": facts_supported,
                "evidence_total": evidence_total,
                "evidence_verified": evidence_verified,
                "citation_support_rate": rate,
                "excluded_out_of_window": self._raw_out_of_window_events,
                "note": "程序只校验来源存在与原文片段匹配，语义支持仍需人工判断；不宣称事实已获独立验证。",
            }
            mark_done(self.state, status, reason, message)
            try:
                stored = self.repo.persist_events(self.state)
                self.state["events"] = stored
            except Exception:
                logger.exception("Failed to persist events for %s", self.state.get("id"))
                add_warning(self.state, "事件写入数据库失败，任务状态已保存。")
            self.repo.save_state(self.state)
            self._finalized = True
        except Exception:
            logger.exception("Finalize failed for run %s", self.state.get("id"))
            raise
        finally:
            self._finalizing = False

    # ---------- utilities ----------

    def _window_start(self) -> datetime:
        days = 1 if self.state.get("window") == "day" else 7
        return self.now - timedelta(days=days)

    def _window_end(self) -> datetime:
        return self.now
