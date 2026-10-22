from __future__ import annotations

from datetime import datetime

from app.state import new_state


def test_full_page_text_is_not_persisted(settings, repo):
    state = new_state(
        run_id="run_storage",
        mode="demo",
        topics=["Agent"],
        window="week",
        settings=settings,
        now=datetime.now(settings.tz),
    )
    state["documents"] = [
        {
            "id": "d1",
            "url": "https://example.com/a",
            "content": "完整正文" * 5000,
            "content_excerpt": "",
            "read_status": "success",
        }
    ]
    repo.create_run(state)
    repo.save_state(state)
    stored = repo.get_state("run_storage")
    assert stored is not None
    assert "content" not in stored["documents"][0]
    assert stored["documents"][0]["content_excerpt"]
    assert len(stored["documents"][0]["content_excerpt"]) <= 1200
    assert "_extracted_doc_ids" not in stored
