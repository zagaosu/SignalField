from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.budgets import (
    BudgetController,
    DailyBudgetExceeded,
    RunBudgetExceeded,
)
from app.config import Settings
from app.db import Repository
from app.state import new_state


def make_state(settings: Settings, mode: str) -> dict:
    return new_state(
        run_id=f"run_budget_{mode}",
        mode=mode,
        topics=["Agent"],
        window="week",
        settings=settings,
        now=datetime.now(settings.tz),
    )


def test_run_limit_is_enforced(settings: Settings, repo: Repository):
    settings.max_reads = 2
    state = make_state(settings, "demo")
    budget = BudgetController(repo, state, settings)
    budget.acquire("read")
    budget.acquire("read")
    with pytest.raises(RunBudgetExceeded):
        budget.acquire("read")
    assert state["usage"]["read_attempts"] == 2


def test_daily_limit_is_enforced_for_live_mode(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        db_path=tmp_path / "budget.sqlite3",
        seed_demo_on_start=False,
        daily_search_budget=2,
    )
    settings.ensure_dirs()
    repo = Repository(settings.resolved_db_path)
    repo.init()
    state = make_state(settings, "live")
    budget = BudgetController(repo, state, settings)
    budget.acquire("search")
    budget.acquire("search")
    with pytest.raises(DailyBudgetExceeded):
        budget.acquire("search")
    assert repo.recent_usage(budget.day)["search_calls"] == 2


def test_zero_daily_cap_means_unlimited_but_usage_is_recorded(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        db_path=tmp_path / "unlimited.sqlite3",
        seed_demo_on_start=False,
        daily_search_budget=0,
        max_searches=10,
    )
    settings.ensure_dirs()
    repo = Repository(settings.resolved_db_path)
    repo.init()
    state = make_state(settings, "live")
    budget = BudgetController(repo, state, settings)
    for _ in range(5):
        budget.acquire("search")
    assert state["usage"]["search_calls"] == 5
    assert repo.recent_usage(budget.day)["search_calls"] == 5


def test_demo_calls_do_not_consume_daily_quota(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        db_path=tmp_path / "demo.sqlite3",
        seed_demo_on_start=False,
        daily_search_budget=1,
    )
    settings.ensure_dirs()
    repo = Repository(settings.resolved_db_path)
    repo.init()
    state = make_state(settings, "demo")
    budget = BudgetController(repo, state, settings)
    budget.acquire("search")
    budget.acquire("search")
    assert state["usage"]["search_calls"] == 2
    assert repo.recent_usage(budget.day)["search_calls"] == 0


def test_token_cost_estimation(settings: Settings, repo: Repository):
    settings.llm_input_price_per_mtok_usd = 2.0
    settings.llm_output_price_per_mtok_usd = 8.0
    state = make_state(settings, "demo")
    budget = BudgetController(repo, state, settings)
    budget.acquire("model")
    budget.record_model_tokens(1_000_000, 500_000)
    assert state["usage"]["tokens_in"] == 1_000_000
    assert state["usage"]["tokens_out"] == 500_000
    assert state["usage"]["estimated_cost_usd"] == pytest.approx(6.0)
