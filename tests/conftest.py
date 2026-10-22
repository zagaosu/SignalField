from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Repository
from app.demo import build_demo_bundle
from app.main import create_app
from app.pipeline.orchestrator import AgentPipeline
from app.state import new_state


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "test.sqlite3",
        seed_demo_on_start=False,
        demo_step_delay_seconds=0.0,
        daily_search_budget=100,
        daily_read_budget=200,
        daily_model_budget=200,
    )


@pytest.fixture
def repo(settings: Settings) -> Repository:
    settings.ensure_dirs()
    repository = Repository(settings.resolved_db_path)
    repository.init()
    return repository


@pytest.fixture
def run_demo(repo: Repository, settings: Settings):
    def _run(
        topics: list[str] | None = None,
        window: str = "week",
        *,
        mode: str = "demo",
        run_id: str | None = None,
    ) -> dict:
        topics = topics or ["Agent", "推理部署", "模型工具"]
        now = datetime.now(settings.tz)
        state = new_state(
            run_id=run_id or f"run_test_{datetime.now().strftime('%H%M%S%f')}",
            mode=mode,
            topics=topics,
            window=window,
            settings=settings,
            now=now,
        )
        repo.create_run(state)
        search_tool, reader, llm, _corpus = build_demo_bundle(now)
        pipeline = AgentPipeline(
            settings=settings,
            repo=repo,
            search_tool=search_tool,
            reader=reader,
            llm=llm,
            now=now,
            delay_seconds=0.0,
        )
        pipeline.run(state)
        return state

    return _run


@pytest.fixture
def client(settings: Settings):
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
