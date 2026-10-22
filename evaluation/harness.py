from __future__ import annotations

import csv
import json
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db import Repository
from app.pipeline.evidence import normalize_key
from app.pipeline.orchestrator import AgentPipeline
from app.state import new_state
from app.tools.base import (
    LLMClient,
    PageReader,
    QuerySpec,
    ReadResult,
    SearchHit,
    SearchTool,
)

from .fixtures import build_scenarios


def _norm_statement(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


PROFILES: dict[str, dict[str, Any]] = {
    "A": {
        "label": "单次搜索直出",
        "description": "1 次搜索、最多 2 篇读取、无补搜。",
        "max_searches": 1,
        "max_reads": 2,
        "max_model_calls": 3,
        "max_gap_rounds": 0,
        "initial_query_limit": 1,
        "initial_read_limit": 2,
        "query_key": "single",
        "adaptive": False,
    },
    "B": {
        "label": "固定查询链",
        "description": "与 C 同搜索/读取/模型预算，固定两条查询，无补搜。",
        "max_searches": 3,
        "max_reads": 5,
        "max_model_calls": 5,
        "max_gap_rounds": 0,
        "initial_query_limit": 2,
        "initial_read_limit": 5,
        "query_key": "fixed",
        "adaptive": False,
    },
    "C": {
        "label": "证据缺口自适应",
        "description": "与 B 同预算，按日期/条件/冲突/读取缺口定向补搜。",
        "max_searches": 3,
        "max_reads": 5,
        "max_model_calls": 5,
        "max_gap_rounds": 2,
        "initial_query_limit": 2,
        "initial_read_limit": 4,
        "query_key": "agent",
        "adaptive": True,
    },
}


class EvalSearch(SearchTool):
    def __init__(self, scenario: dict):
        self.scenario = scenario

    def search(self, spec: QuerySpec, *, window: str, limit: int) -> list[SearchHit]:
        docs = self.scenario["gap_docs"] if spec.round > 0 else self.scenario["initial_docs"]
        hits = []
        for doc in docs[:limit]:
            hits.append(
                SearchHit(
                    title=doc["title"],
                    url=doc["url"],
                    snippet=doc["content"][:180],
                    score=0.9,
                    published_date=doc["published_at"],
                    domain=doc["domain"],
                )
            )
        return hits


class EvalReader(PageReader):
    def __init__(self, scenario: dict):
        self.scenario = scenario
        self.docs = {
            doc["url"]: doc
            for doc in [*scenario["initial_docs"], *scenario["gap_docs"]]
        }

    def read(self, url: str, *, timeout_seconds: float | None = None) -> ReadResult:
        doc = self.docs.get(url)
        if not doc:
            return ReadResult(ok=False, url=url, error="固定材料中没有这个页面")
        if doc.get("fail_read"):
            return ReadResult(ok=False, url=url, error="模拟正文读取失败（需要登录）")
        return ReadResult(
            ok=True,
            url=url,
            final_url=url,
            title=doc["title"],
            content=doc["content"],
            published_at=doc["published_at"],
            language="zh",
            content_type="text/html",
            byte_size=len(doc["content"].encode("utf-8")),
        )


class EvalLLM(LLMClient):
    """Deterministic extractor constrained by the docs that were actually read.

    This is intentionally a test double, not a model. It isolates retrieval
    policy from generation variance.
    """

    def __init__(self, scenario: dict, profile: str):
        self.scenario = scenario
        self.profile = profile

    @staticmethod
    def _usage() -> dict:
        return {"tokens_in": 0, "tokens_out": 0}

    def plan_queries(self, context: dict[str, Any]) -> tuple[dict, dict]:
        key = PROFILES[self.profile]["query_key"]
        queries = []
        for text in self.scenario["queries"][key][: context["limit"]]:
            queries.append(
                {
                    "text": text,
                    "purpose": f"固定评测查询：{self.scenario['name']}",
                    "strategy": "open" if not queries else "official",
                    "topic": self.scenario["topic"],
                    "language": "zh",
                    "domains": [],
                }
            )
        return {"queries": queries, "notes": "固定回放计划"}, self._usage()

    def _present_docs(self, context: dict) -> list[dict]:
        url_to_key = {
            doc["url"]: doc["key"]
            for doc in [*self.scenario["initial_docs"], *self.scenario["gap_docs"]]
        }
        key_to_actual = {}
        for doc in context.get("documents", []):
            key = url_to_key.get(doc["url"])
            if key:
                key_to_actual[key] = doc["id"]
        all_docs = [
            *self.scenario["initial_docs"],
            *self.scenario["gap_docs"],
        ]
        return [
            {**doc, "_actual_id": key_to_actual[doc["key"]]}
            for doc in all_docs
            if doc["key"] in key_to_actual
        ]

    def extract_events(self, context: dict[str, Any]) -> tuple[dict, dict]:
        event_info = self.scenario.get("event")
        present = self._present_docs(context)
        if not event_info or not present:
            return {"events": [], "notes": "没有可抽取的固定页面"}, self._usage()

        gap_present = any(doc["key"] in {d["key"] for d in self.scenario["gap_docs"]} for doc in present)
        fact_map: dict[str, dict] = {}
        for doc in present:
            for fact in doc["facts"]:
                key = f"{_norm_statement(fact['statement'])}|{_norm_statement(fact.get('conditions', ''))}"
                if key not in fact_map:
                    fact_map[key] = {
                        "statement": fact["statement"],
                        "category": fact["category"],
                        "conditions": fact.get("conditions", ""),
                        "evidence": [],
                    }
                fact_map[key]["evidence"].append(
                    {"document_id": doc["_actual_id"], "quote": fact["quote"]}
                )
        if not fact_map:
            return {"events": [], "notes": "没有事实"}, self._usage()

        date_doc = None
        for doc in present:
            if doc.get("event_date_offset") is not None:
                date_doc = doc
                if doc["key"] in {d["key"] for d in self.scenario["gap_docs"]}:
                    break
        date_iso = date_doc.get("_event_date") if date_doc else None
        primary = next(
            (doc for doc in present if doc["key"] in {d["key"] for d in self.scenario["gap_docs"]}),
            present[0],
        )
        unresolved = [] if gap_present else list(event_info.get("initial_unresolved", []))
        resolved = list(event_info.get("resolved_unresolved", [])) if gap_present else []
        event = {
            "event_key": event_info["event_key"],
            "title": event_info["title"],
            "project": event_info["project"],
            "topic": event_info["topic"],
            "event_type": event_info["event_type"],
            "event_date": date_iso,
            "date_confidence": "confirmed" if date_iso else "unknown",
            "summary": event_info["resolved_summary"] if gap_present else event_info["base_summary"],
            "why_it_matters": "固定评测材料中的技术变化，仅用于比较检索策略。",
            "confidence": "high",
            "facts": list(fact_map.values()),
            "unresolved": unresolved,
            "resolved_unresolved": resolved,
            "primary_document_id": primary["_actual_id"],
        }
        return {"events": [event], "notes": "确定性回放抽取"}, self._usage()

    def analyze_gaps(self, context: dict[str, Any]) -> tuple[dict, dict]:
        if self.profile != "C":
            return {"gaps": [], "notes": "基线不补搜"}, self._usage()
        event_info = self.scenario.get("event")
        gaps = context.get("events", [])
        if not event_info or not event_info.get("gap_query") or not gaps:
            return {"gaps": [], "notes": "无缺口"}, self._usage()
        reason = event_info.get("gap_reason")
        needed = False
        if reason == "ambiguous_date":
            needed = any(not event.get("event_date") for event in gaps)
        elif reason == "missing_conditions":
            needed = any(
                fact.get("category") == "performance" and not (fact.get("conditions") or "").strip()
                for event in gaps
                for fact in event.get("facts", [])
            )
        elif reason == "conflict":
            needed = any(
                any("冲突" in item for item in event.get("unresolved", []))
                for event in gaps
            )
        if not needed:
            return {"gaps": [], "notes": "缺口已解决"}, self._usage()
        return {
            "gaps": [
                {
                    "reason_code": reason,
                    "description": f"{self.scenario['name']}的缺口需要原始资料验证。",
                    "topic": self.scenario["topic"],
                    "priority": "high",
                    "query": {
                        "text": event_info["gap_query"],
                        "purpose": event_info.get("gap_purpose", "验证缺口"),
                        "strategy": "official",
                        "domains": [],
                    },
                }
            ],
            "notes": "固定缺口补搜",
        }, self._usage()


def _profile_settings(profile: str, directory: Path) -> Settings:
    cfg = PROFILES[profile]
    return Settings(
        data_dir=directory,
        db_path=directory / "eval.sqlite3",
        seed_demo_on_start=False,
        demo_step_delay_seconds=0.0,
        max_searches=cfg["max_searches"],
        max_reads=cfg["max_reads"],
        max_model_calls=cfg["max_model_calls"],
        max_gap_rounds=cfg["max_gap_rounds"],
        initial_query_limit=cfg["initial_query_limit"],
        initial_read_limit=cfg["initial_read_limit"],
        max_events=3,
        daily_search_budget=1000,
        daily_read_budget=1000,
        daily_model_budget=1000,
    )


def _prior_event(scenario: dict, now: datetime) -> dict:
    event_info = scenario["event"]
    first_doc = scenario["initial_docs"][0]
    facts = []
    for statement in event_info["reference_facts"]:
        matching = next(
            (fact for fact in first_doc["facts"] if fact["statement"] == statement),
            first_doc["facts"][0],
        )
        facts.append(
            {
                "statement": statement,
                "category": matching.get("category", "other"),
                "conditions": matching.get("conditions", ""),
                "status": "supported",
                "evidence": [
                    {
                        "document_id": "prior_d1",
                        "quote": matching["quote"],
                        "verified": True,
                        "url": first_doc["url"],
                        "title": first_doc["title"],
                        "domain": first_doc["domain"],
                    }
                ],
            }
        )
    return {
        "event_key": event_info["event_key"],
        "title": event_info["title"],
        "project": event_info["project"],
        "topic": event_info["topic"],
        "summary": event_info["base_summary"],
        "event_date": (now.date() + timedelta(days=event_info["reference_date_offset"])).isoformat(),
        "date_confidence": "confirmed",
        "change_type": "new",
        "source_count": 1,
        "independent_source_count": 1,
        "confidence_score": 0.85,
        "facts": facts,
        "unresolved": [],
        "sources": [
            {
                "document_id": "prior_d1",
                "title": first_doc["title"],
                "domain": first_doc["domain"],
                "url": first_doc["url"],
                "role": "primary",
            }
        ],
    }


def _preload_prior(repo: Repository, scenario: dict, settings: Settings, now: datetime, run_id: str) -> None:
    prior_state = new_state(
        run_id=run_id,
        mode="demo",
        topics=[scenario["topic"]],
        window="week",
        settings=settings,
        now=now - timedelta(seconds=1),
    )
    repo.create_run(prior_state)
    prior_state["events"] = [_prior_event(scenario, now)]
    repo.persist_events(prior_state)
    prior_state["status"] = "completed"
    prior_state["stop_reason"] = "coverage_sufficient"
    repo.save_state(prior_state)
    repo.mark_run_read(run_id)


def _scenario_docs_with_dates(scenario: dict, now: datetime) -> dict:
    for group in ("initial_docs", "gap_docs"):
        for doc in scenario[group]:
            doc["published_at"] = (
                now.date() + timedelta(days=doc["published_offset"])
            ).isoformat()
            doc["_event_date"] = (
                now.date() + timedelta(days=doc["event_date_offset"])
            ).isoformat() if doc.get("event_date_offset") is not None else None
    return scenario


def _expected_date(scenario: dict, now: datetime) -> str | None:
    event_info = scenario.get("event")
    if not event_info or event_info.get("reference_date_offset") is None:
        return None
    return (now.date() + timedelta(days=event_info["reference_date_offset"])).isoformat()


def _evaluate_run(
    *,
    profile: str,
    scenario: dict,
    state: dict,
    repo: Repository,
    now: datetime,
    duration: float,
) -> dict:
    events = repo.get_run_events(state["id"])
    event_info = scenario.get("event")
    reference_keys = (
        [normalize_key(event_info["event_key"])]
        if event_info and event_info.get("expected_change") is not None
        else []
    )
    reference_facts = (
        event_info.get("reference_facts", [])
        if event_info and event_info.get("expected_change") is not None
        else []
    )
    ref_conditions = event_info.get("reference_conditions", {}) if event_info else {}
    produced_keys = [event.get("event_key") for event in events]
    matched_produced = [event for event in events if event.get("event_key") in reference_keys]
    matched_refs = {event["event_key"] for event in matched_produced}
    expected_date = _expected_date(scenario, now)

    produced_facts = [
        fact
        for event in events
        for fact in event.get("facts", [])
        if fact.get("status") == "supported"
    ]
    covered_ref_facts = 0
    for statement in reference_facts:
        matching = next(
            (fact for fact in produced_facts if _norm_statement(fact.get("statement")) == _norm_statement(statement)),
            None,
        )
        if not matching:
            continue
        expected_conditions = ref_conditions.get(statement, "")
        if expected_conditions:
            actual_conditions = _norm_statement(matching.get("conditions", ""))
            required = [_norm_statement(part) for part in expected_conditions.split("、") if part.strip()]
            if not all(part in actual_conditions for part in required):
                continue
        covered_ref_facts += 1

    time_fit = sum(
        1
        for event in events
        if expected_date is None or event.get("event_date") == expected_date
    )
    actual_change = matched_produced[0].get("change_type") if matched_produced else (events[0].get("change_type") if events else None)
    expected_change = event_info.get("expected_change") if event_info else None
    if expected_change is None:
        change_correct = len(events) == 0
    else:
        change_correct = bool(matched_produced) and actual_change == expected_change

    duplicate_count = len(produced_keys) - len(set(produced_keys))
    verification = state.get("verification", {})
    unread = repo.unread_updates(limit=100)
    resolved_gaps = [gap for gap in state.get("gaps", []) if gap.get("status") == "resolved"]
    actions = state.get("actions", [])
    return {
        "profile": profile,
        "profile_label": PROFILES[profile]["label"],
        "scenario": scenario["id"],
        "case_type": scenario["case_type"],
        "scenario_name": scenario["name"],
        "topic": scenario["topic"],
        "status": state.get("status"),
        "stop_reason": state.get("stop_reason"),
        "event_count": len(events),
        "events": [
            {
                "id": event.get("id"),
                "event_key": event.get("event_key"),
                "title": event.get("title"),
                "event_date": event.get("event_date"),
                "date_confidence": event.get("date_confidence"),
                "change_type": event.get("change_type"),
                "facts": [fact.get("statement") for fact in event.get("facts", [])],
                "sources": [source.get("domain") for source in event.get("sources", [])],
            }
            for event in events
        ],
        "reference_count": len(reference_keys),
        "matched_reference_count": len(matched_refs),
        "matched_produced_count": len(matched_produced),
        "false_positive_events": len(events) - len(matched_produced),
        "time_fit_count": time_fit,
        "reference_fact_count": len(reference_facts),
        "covered_reference_facts": covered_ref_facts,
        "citation_support_rate": verification.get("citation_support_rate"),
        "evidence_total": verification.get("evidence_total", 0),
        "evidence_verified": verification.get("evidence_verified", 0),
        "change_correct": change_correct,
        "expected_change": expected_change,
        "actual_change": actual_change,
        "duplicate_count": duplicate_count,
        "merged_duplicate_docs": sum(
            1 for doc in state.get("documents", []) if doc.get("duplicate_of")
        ),
        "unread_notifications": len(unread),
        "resolved_gaps": len(resolved_gaps),
        "gap_count": len(state.get("gaps", [])),
        "topup_actions": len(actions),
        "topup_new_facts": sum(action.get("new_facts", 0) for action in actions),
        "search_calls": state.get("usage", {}).get("search_calls", 0),
        "read_attempts": state.get("usage", {}).get("read_attempts", 0),
        "model_calls": state.get("usage", {}).get("model_calls", 0),
        "tokens_in": state.get("usage", {}).get("tokens_in", 0),
        "tokens_out": state.get("usage", {}).get("tokens_out", 0),
        "cost_usd": state.get("usage", {}).get("estimated_cost_usd", 0.0),
        "duration_seconds": round(duration, 4),
        "notes": scenario.get("notes", ""),
    }


def run_profile(profile: str, scenario: dict, now: datetime, directory: Path) -> dict:
    settings = _profile_settings(profile, directory)
    settings.ensure_dirs()
    repo = Repository(settings.resolved_db_path)
    repo.init()
    scenario = _scenario_docs_with_dates(scenario, now)
    if scenario.get("prior"):
        _preload_prior(repo, scenario, settings, now, f"prior_{scenario['id']}")
    state = new_state(
        run_id=f"eval_{profile}_{scenario['id']}",
        mode="demo",
        topics=[scenario["topic"]],
        window="week",
        settings=settings,
        now=now,
    )
    repo.create_run(state)
    pipeline = AgentPipeline(
        settings=settings,
        repo=repo,
        search_tool=EvalSearch(scenario),
        reader=EvalReader(scenario),
        llm=EvalLLM(scenario, profile),
        now=now,
        delay_seconds=0,
    )
    started = time.perf_counter()
    pipeline.run(state)
    duration = time.perf_counter() - started
    return _evaluate_run(
        profile=profile,
        scenario=scenario,
        state=state,
        repo=repo,
        now=now,
        duration=duration,
    )


def _aggregate(results: list[dict], profile: str) -> dict:
    subset = [item for item in results if item["profile"] == profile]
    produced = sum(item["event_count"] for item in subset)
    matched = sum(item["matched_produced_count"] for item in subset)
    refs = sum(item["reference_count"] for item in subset)
    refs_matched = sum(item["matched_reference_count"] for item in subset)
    ref_facts = sum(item["reference_fact_count"] for item in subset)
    covered_facts = sum(item["covered_reference_facts"] for item in subset)
    evidence_total = sum(item["evidence_total"] for item in subset)
    evidence_verified = sum(item["evidence_verified"] for item in subset)
    time_fit = sum(item["time_fit_count"] for item in subset)
    duplicates = sum(item["duplicate_count"] for item in subset)
    return {
        "profile": profile,
        "label": PROFILES[profile]["label"],
        "scenarios": len(subset),
        "events": produced,
        "reference_events": refs,
        "reference_event_coverage": round(refs_matched / refs, 4) if refs else None,
        "event_precision": round(matched / produced, 4) if produced else None,
        "time_fit_rate": round(time_fit / produced, 4) if produced else None,
        "reference_fact_coverage": round(covered_facts / ref_facts, 4) if ref_facts else None,
        "citation_support_rate": round(evidence_verified / evidence_total, 4) if evidence_total else None,
        "duplicate_rate": round(duplicates / produced, 4) if produced else 0.0,
        "merged_duplicate_docs": sum(item["merged_duplicate_docs"] for item in subset),
        "change_judgment_accuracy": round(
            sum(1 for item in subset if item["change_correct"]) / len(subset), 4
        )
        if subset
        else None,
        "total_unread_notifications": sum(item["unread_notifications"] for item in subset),
        "resolved_gaps": sum(item["resolved_gaps"] for item in subset),
        "gap_count": sum(item["gap_count"] for item in subset),
        "total_searches": sum(item["search_calls"] for item in subset),
        "total_reads": sum(item["read_attempts"] for item in subset),
        "total_model_calls": sum(item["model_calls"] for item in subset),
        "avg_searches": round(sum(item["search_calls"] for item in subset) / len(subset), 2)
        if subset
        else 0,
        "avg_reads": round(sum(item["read_attempts"] for item in subset) / len(subset), 2)
        if subset
        else 0,
        "avg_model_calls": round(sum(item["model_calls"] for item in subset) / len(subset), 2)
        if subset
        else 0,
        "total_duration_seconds": round(sum(item["duration_seconds"] for item in subset), 4),
        "total_tokens_in": sum(item["tokens_in"] for item in subset),
        "total_tokens_out": sum(item["tokens_out"] for item in subset),
        "estimated_cost_usd": round(sum(item["cost_usd"] for item in subset), 6),
    }


def _markdown_report(results: list[dict], aggregates: list[dict], batch_id: str) -> str:
    lines = [
        "# SignalField 回放评测报告",
        "",
        f"- 批次：`{batch_id}`",
        "- 材料：8 个合成固定场景，URL 使用保留 `.invalid` 域名。",
        "- 模型：确定性抽取替身，未调用远程 LLM；搜索服务亦未调用。",
        "- 目的：隔离并检验检索策略、证据闭环与补搜决策，不代表线上模型或真实搜索效果。",
        "",
        "## 汇总",
        "",
        "| 策略 | 参考事件覆盖 | 事件精确率 | 时间符合 | 参考事实覆盖 | 引用支持率 | 事件重复率 | 合并转载文档 | 变更判断 | 平均搜索/读取/模型 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def pct(value):
        return "—" if value is None else f"{value * 100:.1f}%"

    for agg in aggregates:
        lines.append(
            "| {label} ({p}) | {cov} | {prec} | {time} | {fact} | {cite} | {dup} | {merged} | {change} | {s}/{r}/{m} |".format(
                label=agg["label"],
                p=agg["profile"],
                cov=pct(agg["reference_event_coverage"]),
                prec=pct(agg["event_precision"]),
                time=pct(agg["time_fit_rate"]),
                fact=pct(agg["reference_fact_coverage"]),
                cite=pct(agg["citation_support_rate"]),
                dup=pct(agg["duplicate_rate"]),
                merged=agg["merged_duplicate_docs"],
                change=pct(agg["change_judgment_accuracy"]),
                s=agg["avg_searches"],
                r=agg["avg_reads"],
                m=agg["avg_model_calls"],
            )
        )
    lines.extend(
        [
            "",
            "## 场景明细",
            "",
            "| 场景 | 策略 | 事件数 | 事件日期 | 覆盖参考事实 | 已解决缺口 | 查询/读取/模型 | 变更判断 | 停止原因 |",
            "|---|---|---:|---|---:|---:|---|---|---|",
        ]
    )
    for item in results:
        lines.append(
            f"| {item['scenario_name']} | {item['profile']} | {item['event_count']} | "
            f"{item['events'][0]['event_date'] if item['events'] else '—'} | "
            f"{item['covered_reference_facts']}/{item['reference_fact_count']} | "
            f"{item['resolved_gaps']}/{item['gap_count']} | "
            f"{item['search_calls']}/{item['read_attempts']}/{item['model_calls']} | "
            f"{'正确' if item['change_correct'] else '需复核'} | {item['stop_reason']} |"
        )
    c_agg = next((item for item in aggregates if item["profile"] == "C"), None)
    b_agg = next((item for item in aggregates if item["profile"] == "B"), None)
    lines.extend(["", "## 自适应补搜的观测", ""])
    if c_agg and b_agg:
        cov_delta = (c_agg["reference_event_coverage"] or 0) - (b_agg["reference_event_coverage"] or 0)
        fact_delta = (c_agg["reference_fact_coverage"] or 0) - (b_agg["reference_fact_coverage"] or 0)
        lines.append(
            f"- C 相对 B：参考事件覆盖 {cov_delta * 100:+.1f} 个百分点；参考事实覆盖 {fact_delta * 100:+.1f} 个百分点。"
        )
        lines.append(
            f"- C 共解决 {c_agg['resolved_gaps']} / {c_agg['gap_count']} 个缺口；额外使用查询与读取均已计入实际调用。"
        )
    lines.extend(
        [
            "- 以上为合成回放上的实测结果，只说明检索策略在该材料上的行为差异，不能外推为线上效果。",
            "",
            "## 必须同时阅读的限制",
            "",
            "1. 抽取器是确定性替身，没有模型幻觉、上下文长度或供应商限流等真实变量。",
            "2. 固定材料由项目维护者编写，参考事件与事实是独立标注，但规模只有 8 个案例。",
            "3. 引用支持率只表示片段逐字匹配，不表示语义支持或独立信源确认。",
            "4. 真实 Tavily/模型评测必须使用 `python -m evaluation.run_live` 单独运行，不能与本次结果混合。",
            "5. 人工相关性、独立确认与变更判断需通过 `annotation_batch.csv` 补标，自动指标不能代替人评。",
            "6. 这不是留出集：8 个场景在开发过程中被用来定位策略问题，C 的满分是开发集结果，不是泛化或线上效果证明。",
            "",
        ]
    )
    return "\n".join(lines)


ANNOTATION_COLUMNS = [
    "batch_id",
    "profile",
    "scenario",
    "case_type",
    "event_id",
    "event_title",
    "topic",
    "event_date",
    "change_type",
    "facts_count",
    "source_domains",
    "auto_time_fit",
    "human_relevance_0_2",
    "human_time_fit_0_1",
    "human_fact_support_0_2",
    "human_independent_confirmation_0_1",
    "human_change_judgment",
    "human_note",
]


def _annotation_rows(results: list[dict], batch_id: str) -> list[dict]:
    rows = []
    for item in results:
        if item["events"]:
            for event in item["events"]:
                rows.append(
                    {
                        "batch_id": batch_id,
                        "profile": item["profile"],
                        "scenario": item["scenario"],
                        "case_type": item["case_type"],
                        "event_id": event.get("id") or event.get("event_key"),
                        "event_title": event.get("title"),
                        "topic": item.get("topic", ""),
                        "event_date": event.get("event_date") or "",
                        "change_type": event.get("change_type") or "",
                        "facts_count": len(event.get("facts", [])),
                        "source_domains": " | ".join(event.get("sources", [])),
                        "auto_time_fit": item["time_fit_count"] > 0,
                        "human_relevance_0_2": "",
                        "human_time_fit_0_1": "",
                        "human_fact_support_0_2": "",
                        "human_independent_confirmation_0_1": "",
                        "human_change_judgment": "",
                        "human_note": "",
                    }
                )
        else:
            rows.append(
                {
                    "batch_id": batch_id,
                    "profile": item["profile"],
                    "scenario": item["scenario"],
                    "case_type": item["case_type"],
                    "event_id": "__NO_EVENT__",
                    "event_title": "",
                    "topic": "",
                    "event_date": "",
                    "change_type": "",
                    "facts_count": 0,
                    "source_domains": "",
                    "auto_time_fit": False,
                    "human_relevance_0_2": "",
                    "human_time_fit_0_1": "",
                    "human_fact_support_0_2": "",
                    "human_independent_confirmation_0_1": "",
                    "human_change_judgment": "",
                    "human_note": "",
                }
            )
    return rows


def run_all(output_dir: Path, profiles: list[str] | None = None) -> dict:
    profiles = profiles or ["A", "B", "C"]
    now = datetime.now(Settings.from_env().tz)
    scenarios = build_scenarios(now)
    batch_id = now.strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="signalfield-eval-") as temp:
        temp_root = Path(temp)
        for scenario in scenarios:
            for profile in profiles:
                result = run_profile(
                    profile,
                    scenario,
                    now,
                    temp_root / profile / scenario["id"],
                )
                results.append(result)
    aggregates = [_aggregate(results, profile) for profile in profiles]
    payload = {
        "batch_id": batch_id,
        "generated_at": now.isoformat(timespec="seconds"),
        "mode": "replay",
        "synthetic": True,
        "remote_calls": 0,
        "scenarios": [
            {
                "id": scenario["id"],
                "case_type": scenario["case_type"],
                "name": scenario["name"],
                "notes": scenario.get("notes", ""),
            }
            for scenario in scenarios
        ],
        "profiles": {profile: PROFILES[profile] for profile in profiles},
        "aggregates": aggregates,
        "results": results,
        "limitations": [
            "确定性模型替身，不代表真实 LLM 能力",
            "8 个合成场景，规模小",
            "引用支持率只校验逐字片段，不等于语义支持或独立验证",
            "实时 Tavily/模型评测需单独运行，不能与本次结果合并",
            "这是开发集而非留出集；C 的得分为开发集结果，不等于泛化能力",
        ],
    }
    json_path = output_dir / "replay_latest.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / f"replay_{batch_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = _markdown_report(results, aggregates, batch_id)
    (output_dir / "replay_latest.md").write_text(report, encoding="utf-8")
    (output_dir / f"replay_{batch_id}.md").write_text(report, encoding="utf-8")

    rows = _annotation_rows(results, batch_id)
    annotation_path = output_dir / "annotation_batch.csv"
    with annotation_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "payload": payload,
        "aggregates": aggregates,
        "json_path": json_path,
        "report": report,
        "annotation_path": annotation_path,
    }
