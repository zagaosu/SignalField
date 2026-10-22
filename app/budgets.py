from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Callable

from .config import Settings
from .db import Repository, local_day


class BudgetError(Exception):
    code = "budget_error"

    def __init__(self, message: str, *, kind: str = "", scope: str = "run"):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.scope = scope


class RunBudgetExceeded(BudgetError):
    code = "run_budget_exceeded"


class DailyBudgetExceeded(BudgetError):
    code = "daily_budget_exceeded"


class TimeBudgetExceeded(BudgetError):
    code = "time_budget_exceeded"


class CancelledError(Exception):
    pass


class BudgetController:
    """Reserve before each external call so parallel work cannot overspend."""

    _KIND_TO_USAGE = {
        "search": "search_calls",
        "read": "read_attempts",
        "model": "model_calls",
    }
    _KIND_TO_RUN_LIMIT = {
        "search": "searches",
        "read": "reads",
        "model": "model_calls",
    }
    _KIND_TO_DAILY_LIMIT = {
        "search": "daily_searches",
        "read": "daily_reads",
        "model": "daily_model_calls",
    }
    _KIND_TO_DAILY_USAGE = {
        "search": "search_calls",
        "read": "read_calls",
        "model": "model_calls",
    }

    def __init__(
        self,
        repo: Repository,
        state: dict,
        settings: Settings,
        on_change: Callable[[], None] | None = None,
    ):
        self.repo = repo
        self.state = state
        self.settings = settings
        self.day = local_day(settings.timezone)
        self._lock = threading.RLock()
        self._model_ticket: int | None = None
        self._on_change = on_change
        self.started_monotonic = datetime.now()
        self.deadline = self.started_monotonic + timedelta(seconds=settings.max_seconds)

    @property
    def live(self) -> bool:
        return self.state.get("mode") == "live"

    @property
    def usage(self) -> dict:
        return self.state["usage"]

    def _run_used(self, kind: str) -> int:
        return int(self.usage.get(self._KIND_TO_USAGE[kind], 0))

    def _run_limit(self, kind: str) -> int:
        return int(self.state["budget"]["limits"][self._KIND_TO_RUN_LIMIT[kind]])

    def remaining_daily(self, kind: str) -> int:
        if not self.live:
            return 10**9
        limit = int(self.state["budget"]["limits"][self._KIND_TO_DAILY_LIMIT[kind]])
        if limit <= 0:
            return 10**9
        used = self.repo.recent_usage(self.day)
        return max(0, limit - int(used[self._KIND_TO_DAILY_USAGE[kind]]))

    def remaining_seconds(self) -> float:
        return max(0.0, (self.deadline - datetime.now()).total_seconds())

    def ensure_capacity(self) -> None:
        with self._lock:
            checks = [
                ("search", "搜索"),
                ("read", "正文读取"),
                ("model", "模型"),
            ]
            for kind, label in checks:
                if self._run_used(kind) >= self._run_limit(kind):
                    raise RunBudgetExceeded(
                        f"本次任务的{label}额度已用完。", kind=kind, scope="run"
                    )
                daily_limit = int(
                    self.state["budget"]["limits"][self._KIND_TO_DAILY_LIMIT[kind]]
                )
                if self.live and daily_limit > 0 and self.remaining_daily(kind) <= 0:
                    raise DailyBudgetExceeded(
                        f"本应用今日{label}保护预算已用完；这不是 DeepSeek 账户余额。"
                        "可在 .env 调整 DAILY_SEARCH_BUDGET 等每日上限。",
                        kind=kind,
                        scope="daily",
                    )
            if self.remaining_seconds() <= 2:
                raise TimeBudgetExceeded("本次任务已接近时间上限。", scope="run")

    def acquire(self, kind: str) -> int:
        with self._lock:
            if self.remaining_seconds() <= 0:
                raise TimeBudgetExceeded("本次任务已达到 120 秒时间上限。", kind=kind, scope="time")
            if self._run_used(kind) >= self._run_limit(kind):
                raise RunBudgetExceeded(
                    f"本次任务的{self._label(kind)}调用上限已达到。",
                    kind=kind,
                    scope="run",
                )
            if self.live:
                daily = self.repo.recent_usage(self.day)
                limit = int(self.state["budget"]["limits"][self._KIND_TO_DAILY_LIMIT[kind]])
                used = int(daily[self._KIND_TO_DAILY_USAGE[kind]])
                if limit > 0 and used >= limit:
                    raise DailyBudgetExceeded(
                        f"本应用今日{self._label(kind)}保护预算已用完（{used}/{limit}）；"
                        "这不是 DeepSeek 账户余额，可在 .env 调整每日上限。",
                        kind=kind,
                        scope="daily",
                    )
            self.usage[self._KIND_TO_USAGE[kind]] += 1
            if self.live:
                self.usage["remote_calls"] += 1
            ticket = self.repo.record_usage(
                self.day,
                self.state["id"],
                kind,
                units=1,
                simulated=not self.live,
            )
            if kind == "search" and self.live and self.settings.tavily_cost_per_call_usd:
                cost = self.settings.tavily_cost_per_call_usd
                self.repo.update_usage_tokens(ticket, 0, 0, cost)
                self.usage["estimated_cost_usd"] += cost
            if kind == "model":
                self._model_ticket = ticket
            if self._on_change:
                self._on_change()
            return ticket

    def record_model_tokens(self, tokens_in: int, tokens_out: int) -> None:
        with self._lock:
            tokens_in = max(0, int(tokens_in or 0))
            tokens_out = max(0, int(tokens_out or 0))
            self.usage["tokens_in"] += tokens_in
            self.usage["tokens_out"] += tokens_out
            cost = (
                tokens_in * self.settings.llm_input_price_per_mtok_usd / 1_000_000
                + tokens_out * self.settings.llm_output_price_per_mtok_usd / 1_000_000
            )
            self.usage["estimated_cost_usd"] += cost
            if self._model_ticket is not None and self.live:
                self.repo.update_usage_tokens(self._model_ticket, tokens_in, tokens_out, cost)
            if self._on_change:
                self._on_change()

    def snapshot(self) -> dict:
        daily = self.repo.recent_usage(self.day) if self.live else None
        return {
            "limits": self.state["budget"]["limits"],
            "used": dict(self.usage),
            "daily": daily,
            "day": self.day,
            "remaining_seconds": int(self.remaining_seconds()),
        }

    @staticmethod
    def _label(kind: str) -> str:
        return {"search": "搜索", "read": "正文读取", "model": "模型"}.get(kind, kind)
