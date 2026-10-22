from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def wait_for_run(client: TestClient, run_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] not in {"queued", "running", "cancelling"}:
            return last
        time.sleep(0.08)
    raise AssertionError(f"run did not finish: {last}")


def test_config_never_exposes_secrets(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    text = response.text
    for secret_name in ("TAVILY_API_KEY=", "LLM_API_KEY=", "sk-"):
        assert secret_name not in text
    data = response.json()
    assert data["modes"]["demo"]["available"] is True
    assert data["modes"]["live"]["available"] is False
    assert "TAVILY_API_KEY" in data["modes"]["live"]["missing"]


def test_deepseek_search_provider_config(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        db_path=tmp_path / "deepseek.sqlite3",
        seed_demo_on_start=False,
        search_provider="deepseek",
        llm_base_url="https://api.deepseek.com",
        llm_model="deepseek-flash",
        llm_api_key="",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        data = client.get("/api/config").json()
        assert data["search_provider"] == "deepseek"
        assert data["search_provider_label"] == "DeepSeek Search"
        assert data["modes"]["live"]["missing"] == ["LLM_API_KEY"]
        assert data["modes"]["live"]["provider_label"] == "DeepSeek Search"
        assert data["modes"]["live"]["model"] == "deepseek-flash"


def test_index_and_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "信号场" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_validation_and_live_config_error(client):
    response = client.post(
        "/api/runs",
        json={"topics": ["A1", "B2", "C3", "D4"], "window": "week", "mode": "demo"},
    )
    assert response.status_code == 422
    response = client.post(
        "/api/runs",
        json={"topics": ["Agent"], "window": "week", "mode": "live"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "config_missing"


def test_demo_run_api_and_read_flow(client):
    response = client.post(
        "/api/runs",
        json={
            "topics": ["Agent", "推理部署"],
            "window": "week",
            "mode": "demo",
            "focus_keywords": ["工具调用", "量化"],
        },
    )
    assert response.status_code == 202
    run_id = response.json()["id"]
    detail = wait_for_run(client, run_id)
    assert detail["status"] == "completed"
    assert detail["mode"] == "demo"
    assert detail["focus_keywords"] == ["工具调用", "量化"]
    assert len(detail["events"]) >= 2
    assert detail["verification"]["evidence_verified"] > 0
    assert "content" not in detail["documents"][0]
    assert detail["documents"][0]["content_excerpt"]
    assert "_extracted_doc_ids" not in detail

    updates = client.get("/api/updates").json()
    assert updates["count"] >= 2
    event_id = detail["events"][0]["id"]
    assert client.post(f"/api/events/{event_id}/read").status_code == 200
    updates_after = client.get("/api/updates").json()
    assert updates_after["count"] < updates["count"]

    assert client.post(f"/api/runs/{run_id}/read").status_code == 200
    assert client.get("/api/updates").json()["count"] == 0

    history = client.get("/api/runs").json()["runs"]
    assert history
    assert history[0]["id"] == run_id
    assert history[0]["card_count"] >= 2

    detail_after = client.get(f"/api/runs/{run_id}").json()
    assert all(event["read_at"] for event in detail_after["events"])


def test_cancel_returns_partial_or_cancelled_run(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        db_path=tmp_path / "cancel.sqlite3",
        seed_demo_on_start=False,
        demo_step_delay_seconds=0.22,
        daily_search_budget=100,
        daily_read_budget=200,
        daily_model_budget=200,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/runs",
            json={"topics": ["推理部署"], "window": "week", "mode": "demo"},
        )
        assert response.status_code == 202
        run_id = response.json()["id"]
        time.sleep(0.35)
        cancel = client.post(f"/api/runs/{run_id}/cancel")
        assert cancel.status_code == 202
        detail = wait_for_run(client, run_id, timeout=8)
        assert detail["status"] == "cancelled"
        assert detail["stop_reason"] == "user_cancel"
