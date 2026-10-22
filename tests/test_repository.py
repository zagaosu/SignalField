from __future__ import annotations

from datetime import datetime

from app.db import Repository
from app.state import new_state


def _fake_event(statement: str) -> dict:
    return {
        "event_key": "demo-project:1.0",
        "title": "Demo Project 1.0",
        "topic": "Agent",
        "summary": "摘要",
        "event_date": "2026-10-20",
        "date_confidence": "confirmed",
        "change_type": "new",
        "source_count": 1,
        "independent_source_count": 1,
        "confidence_score": 0.8,
        "facts": [
            {
                "statement": statement,
                "conditions": "",
                "status": "supported",
                "evidence": [
                    {
                        "document_id": "d1",
                        "quote": statement,
                        "verified": True,
                        "url": "https://example.com/a",
                    }
                ],
            }
        ],
        "unresolved": [],
        "sources": [{"document_id": "d1", "domain": "example.com", "title": "A"}],
    }


def test_event_update_classification_and_read_state(settings, repo: Repository):
    now = datetime.now(settings.tz)
    first = new_state(
        run_id="run_first", mode="demo", topics=["Agent"], window="week", settings=settings, now=now
    )
    repo.create_run(first)
    first["events"] = [_fake_event("第一版事实。")]
    repo.persist_events(first)
    repo.save_state(first)
    event_id = first["events"][0]["id"]
    assert repo.get_run_events("run_first")[0]["change_type"] == "new"
    assert repo.unread_updates()[0]["id"] == event_id

    second = new_state(
        run_id="run_second", mode="demo", topics=["Agent"], window="week", settings=settings, now=now
    )
    repo.create_run(second)
    second["events"] = [_fake_event("第一版事实。")]
    repo.persist_events(second)
    repo.save_state(second)
    unchanged = repo.get_run_events("run_second")[0]
    assert unchanged["change_type"] == "unchanged"
    assert unchanged["read_at"] is not None
    assert len(repo.unread_updates()) == 1

    third = new_state(
        run_id="run_third", mode="demo", topics=["Agent"], window="week", settings=settings, now=now
    )
    repo.create_run(third)
    third["events"] = [_fake_event("第一版事实。"), _fake_event("新增的第二条事实。")]
    third["events"] = [third["events"][0]]
    third["events"][0]["facts"].append(
        {
            "statement": "新增的第二条事实。",
            "conditions": "",
            "status": "supported",
            "evidence": [{"document_id": "d1", "quote": "新增的第二条事实。", "verified": True}],
        }
    )
    repo.persist_events(third)
    repo.save_state(third)
    updated = repo.get_run_events("run_third")[0]
    assert updated["change_type"] == "updated"
    assert "新增" in updated["change_note"]

    repo.mark_event_read(event_id)
    assert repo.get_run_events("run_first")[0]["read_at"]
    repo.mark_run_read("run_third")
    assert repo.unread_updates() == []


def test_interrupted_runs_are_recovered(settings, repo: Repository):
    now = datetime.now(settings.tz)
    state = new_state(
        run_id="run_interrupted", mode="demo", topics=["Agent"], window="week", settings=settings, now=now
    )
    state["status"] = "running"
    repo.create_run(state)
    changed = repo.mark_interrupted_runs()
    assert changed == 1
    row = repo.get_run_row("run_interrupted")
    assert row["status"] == "partial"
    assert row["stop_reason"] == "server_restart"
    assert "重启" in row["stop_message"]
