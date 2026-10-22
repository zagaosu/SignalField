from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.pipeline.evidence import (
    event_too_old,
    is_near_duplicate,
    merge_event,
    quote_verified,
    same_event,
)


def test_quote_matching_normalizes_width_and_whitespace_but_not_meaning():
    content = "官方基准显示，在 24GB RTX 4090、batch size 1、2K 上下文条件下，延迟降低 31%。"
    assert quote_verified("官方基准显示, 在 24GB RTX 4090、batch size 1、2K 上下文条件下,延迟降低 31%。", content)
    assert not quote_verified("官方基准显示，延迟降低 50%。", content)
    assert not quote_verified("延迟降低 31%", "文章完全没有提到这个数字。")


def test_near_duplicate_repost_is_detected():
    first = {
        "id": "d1",
        "read_status": "success",
        "title": "Aster Agent Kit 0.8 发布",
        "content": "Aster Agent Kit 0.8 默认开启工具权限网关。" * 10,
        "content_hash": "abc",
    }
    repost = {
        "id": "d2",
        "read_status": "success",
        "title": "转载：Aster Agent Kit 0.8 发布",
        "content": "本文转载。\n" + "Aster Agent Kit 0.8 默认开启工具权限网关。" * 10,
        "content_hash": "def",
    }
    assert is_near_duplicate(repost, [first]) == "d1"


def test_merge_tracks_resolved_gaps_and_new_facts():
    target = {
        "event_key": "x:1",
        "project": "X",
        "title": "X 1.0 发布",
        "event_type": "release",
        "event_date": "2026-10-20",
        "date_confidence": "confirmed",
        "summary": "旧摘要",
        "facts": [
            {
                "statement": "X 1.0 发布。",
                "conditions": "",
                "status": "supported",
                "evidence": [{"document_id": "d1", "quote": "X 1.0 发布。"}],
            }
        ],
        "unresolved": ["8GB 设备支持边界不明确。"],
        "sources": [
            {
                "document_id": "d1",
                "domain": "x.example",
                "title": "X 1.0",
                "url": "https://x.example/1",
            }
        ],
        "date_conflict": False,
        "confidence_score": 0.5,
    }
    incoming = {
        "event_key": "x:1",
        "project": "X",
        "title": "X 1.0 发布",
        "event_type": "release",
        "event_date": "2026-10-20",
        "date_confidence": "confirmed",
        "summary": "新摘要：官方说明了 8GB 回退。",
        "facts": [
            {
                "statement": "8GB 设备会回退到 FP16。",
                "conditions": "8GB 显存",
                "status": "supported",
                "evidence": [{"document_id": "d2", "quote": "8GB 设备会回退到 FP16。"}],
            }
        ],
        "unresolved": [],
        "resolved_unresolved": ["8GB 设备支持边界不明确。"],
        "sources": [
            {
                "document_id": "d2",
                "domain": "x.example",
                "title": "Compatibility",
                "url": "https://x.example/docs",
            }
        ],
        "date_conflict": False,
        "confidence_score": 0.8,
    }
    merged = merge_event(target, incoming)
    assert merged["unresolved"] == []
    assert len(merged["facts"]) == 2
    assert merged["summary"].startswith("新摘要")
    assert merged["source_count"] == 2
    assert merged["independent_source_count"] == 1


def test_same_event_uses_stable_project_and_version():
    left = {
        "event_key": "lattice-inference:2.4",
        "project": "Lattice Inference",
        "title": "Lattice Inference 2.4 发布",
        "event_type": "release",
        "event_date": "2026-10-20",
    }
    right = {
        "event_key": "another-key",
        "project": "Lattice Inference",
        "title": "Lattice 2.4 更新说明",
        "event_type": "release",
        "event_date": "2026-10-20",
    }
    assert same_event(left, right)


def test_window_boundary_is_date_based():
    now = datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    start = now.replace(day=14, hour=0)
    from datetime import date

    assert not event_too_old(date(2026, 10, 20), start, now)
    assert event_too_old(date(2026, 10, 1), start, now)
    assert not event_too_old(None, start, now)
