from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from .config import Settings
from .models import iso_now, utc_now, window_bounds

STAGE_PROGRESS: dict[str, tuple[int, str]] = {
    "created": (2, "准备任务"),
    "planning": (8, "规划检索策略"),
    "searching": (24, "搜索候选资料"),
    "reading": (46, "读取并筛选正文"),
    "extracting": (64, "聚合事件与事实"),
    "checking_gaps": (72, "检查证据缺口"),
    "gap_searching": (79, "定向补搜"),
    "gap_reading": (83, "读取补充资料"),
    "verifying": (94, "核验引用"),
    "ranking": (97, "排序与生成卡片"),
    "done": (100, "完成"),
}

# Explicit graph edges. Any non-terminal stage may enter final verification so
# cancellations, budget exhaustion and tool failures still produce a terminal
# state with partial results. Repeated stages are no-ops.
STAGE_TRANSITIONS: dict[str, set[str]] = {
    "created": {"planning", "verifying", "done"},
    "planning": {"searching", "verifying", "done"},
    "searching": {"reading", "verifying", "done"},
    "reading": {"extracting", "checking_gaps", "verifying", "done"},
    "extracting": {"checking_gaps", "verifying", "done"},
    "checking_gaps": {"gap_searching", "verifying", "done"},
    "gap_searching": {"gap_reading", "verifying", "done"},
    "gap_reading": {"extracting", "gap_searching", "checking_gaps", "verifying", "done"},
    "verifying": {"done"},
    "done": {"done"},
}

PUBLIC_DOC_EXCERPT = 700


def new_state(
    *,
    run_id: str,
    mode: str,
    topics: list[str],
    window: str,
    settings: Settings,
    now: datetime | None = None,
    focus_keywords: list[str] | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    start, end = window_bounds(window, now)
    demo = mode == "demo"
    state: dict[str, Any] = {
        "id": run_id,
        "version": 1,
        "mode": mode,
        "topics": topics,
        "focus_keywords": list(focus_keywords or []),
        "window": window,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "status": "queued",
        "stage": "created",
        "stage_history": [
            {"from": None, "to": "created", "at": iso_now(), "message": "任务已创建"}
        ],
        "created_at": iso_now(),
        "started_at": None,
        "finished_at": None,
        "stop_reason": None,
        "stop_message": None,
        "cancel_requested": False,
        "warnings": [],
        "plan_notes": "",
        "queries": [],
        "documents": [],
        "events": [],
        "gaps": [],
        "actions": [],
        "usage": {
            "search_calls": 0,
            "read_attempts": 0,
            "model_calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "estimated_cost_usd": 0.0,
            "remote_calls": 0,
            "simulated": demo,
        },
        "budget": {
            "limits": settings.public_limits(),
        },
        "verification": {
            "facts_total": 0,
            "facts_supported": 0,
            "evidence_total": 0,
            "evidence_verified": 0,
            "citation_support_rate": None,
            "note": "程序只校验来源存在与原文片段匹配，不宣称事实已被独立验证。",
        },
        "progress": {"percent": 2, "stage": "created", "message": "任务已创建"},
        "demo_notice": (
            "演示使用虚构样例，未执行实时搜索，不消耗远程服务额度；日期均为样例日期。"
            if demo
            else None
        ),
    }
    return state


def set_stage(state: dict, stage: str, message: str, percent: int | None = None) -> None:
    previous = state.get("stage", "created")
    if stage != previous:
        if stage not in STAGE_TRANSITIONS.get(previous, set()):
            add_warning(state, f"检测到非预期状态转移：{previous} → {stage}")
        state.setdefault("stage_history", []).append(
            {"from": previous, "to": stage, "at": iso_now(), "message": message}
        )
        state["stage"] = stage
    fallback = STAGE_PROGRESS.get(stage, (state.get("progress", {}).get("percent", 0), ""))
    state["status"] = "running" if state.get("status") in {"queued", "running"} else state.get("status")
    state["progress"] = {
        "percent": percent if percent is not None else fallback[0],
        "stage": stage,
        "message": message,
    }


def add_warning(state: dict, message: str) -> None:
    message = str(message).strip()
    if message and message not in state["warnings"]:
        state["warnings"].append(message[:500])


def mark_done(state: dict, status: str, stop_reason: str, message: str) -> None:
    if state.get("stage") != "done":
        state.setdefault("stage_history", []).append(
            {"from": state.get("stage"), "to": "done", "at": iso_now(), "message": message}
        )
    state["status"] = status
    state["stop_reason"] = stop_reason
    state["stop_message"] = message
    state["finished_at"] = iso_now()
    state["stage"] = "done"
    state["progress"] = {"percent": 100, "stage": "done", "message": message}


def public_state(
    state: dict,
    *,
    events: list[dict] | None = None,
    daily_usage: dict | None = None,
    include_content: bool = False,
) -> dict:
    """Return a browser-safe view. Credentials never live in the state."""
    data = copy.deepcopy(state)
    for key in [key for key in data if str(key).startswith("_")]:
        data.pop(key, None)
    documents = []
    for doc in data.get("documents", []):
        item = dict(doc)
        content = item.pop("content", "")
        item["content_excerpt"] = (content or item.get("content_excerpt", ""))[:PUBLIC_DOC_EXCERPT]
        item.pop("full_content", None)
        documents.append(item)
    data["documents"] = documents
    if events is not None:
        data["events"] = events
    if daily_usage is not None:
        data["daily_usage"] = daily_usage
    if not include_content:
        data.pop("raw_plan", None)
    # Derived convenience fields for the UI.
    usage = data.get("usage", {})
    limits = data.get("budget", {}).get("limits", {})
    data["budget_view"] = {
        "searches": {
            "used": usage.get("search_calls", 0),
            "limit": limits.get("searches", 0),
            "remaining": max(0, limits.get("searches", 0) - usage.get("search_calls", 0)),
        },
        "reads": {
            "used": usage.get("read_attempts", 0),
            "limit": limits.get("reads", 0),
            "remaining": max(0, limits.get("reads", 0) - usage.get("read_attempts", 0)),
        },
        "model_calls": {
            "used": usage.get("model_calls", 0),
            "limit": limits.get("model_calls", 0),
            "remaining": max(0, limits.get("model_calls", 0) - usage.get("model_calls", 0)),
        },
        "gap_rounds": {
            "used": max((q.get("round", 0) for q in data.get("queries", [])), default=0),
            "limit": limits.get("gap_rounds", 0),
        },
    }
    if data.get("created_at"):
        try:
            created = datetime.fromisoformat(data["created_at"])
            finished = datetime.fromisoformat(data["finished_at"]) if data.get("finished_at") else utc_now()
            data["elapsed_seconds"] = max(0, int((finished - created).total_seconds()))
        except (ValueError, TypeError):
            data["elapsed_seconds"] = None
    return data


def should_stop(state: dict) -> bool:
    return bool(state.get("cancel_requested")) or state.get("status") in {"cancelling", "cancelled"}
