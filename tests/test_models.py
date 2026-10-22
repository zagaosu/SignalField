from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import TOPIC_PRESETS, RunCreate, parse_event_date


def test_topics_are_cleaned_and_deduplicated():
    payload = RunCreate(
        topics=["<b>RAG 评测</b>", "RAG   评测", "\x00Agent"],
        window="week",
        mode="demo",
    )
    assert payload.topics == ["RAG 评测", "Agent"]


def test_max_three_topics_after_deduplication():
    with pytest.raises(ValidationError):
        RunCreate(topics=["A1", "B2", "C3", "D4"], window="day", mode="demo")


def test_topic_length_and_empty_values():
    with pytest.raises(ValidationError):
        RunCreate(topics=["x" * 25], mode="demo")
    with pytest.raises(ValidationError):
        RunCreate(topics=["   "], mode="demo")


def test_focus_keywords_are_cleaned_and_capped():
    payload = RunCreate(
        topics=["Agent"],
        focus_keywords=[" 工具调用 ", "工具调用", "<b>量化</b>"],
        window="week",
        mode="demo",
    )
    assert payload.focus_keywords == ["工具调用", "量化"]
    with pytest.raises(ValidationError):
        RunCreate(
            topics=["Agent"],
            focus_keywords=["一", "二", "三", "四"],
            window="week",
            mode="demo",
        )


def test_extended_direction_presets_are_available():
    labels = [item["label"] for item in TOPIC_PRESETS]
    assert labels[:3] == ["Agent", "推理部署", "模型工具"]
    assert {
        "多模态",
        "RAG 与数据",
        "评测与安全",
        "开源模型",
        "AI 编程",
        "生活",
        "运动",
        "新闻",
        "财经",
        "娱乐",
        "科学",
        "健康",
        "汽车",
        "旅行",
        "教育",
        "游戏",
        "时尚",
    }.issubset(labels)
    assert len(labels) == len(set(labels)) == 20


def test_event_date_parsing_accepts_chinese_and_rejects_future():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert parse_event_date("2026年10月20日", now).isoformat() == "2026-10-20"
    assert parse_event_date("2026/10/19", now).isoformat() == "2026-10-19"
    assert parse_event_date("2027-01-01", now) is None
    assert parse_event_date("not-a-date", now) is None
