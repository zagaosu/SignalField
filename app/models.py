from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TOPIC_PRESETS: list[dict[str, str]] = [
    {
        "id": "agent",
        "label": "Agent",
        "description": "编排、工具调用、评测与记忆",
        "hint": "Agent 框架 / 工具调用 / 评测 / 记忆",
    },
    {
        "id": "inference",
        "label": "推理部署",
        "description": "推理引擎、量化与端侧部署",
        "hint": "推理引擎 / 量化 / 端侧部署",
    },
    {
        "id": "model_tools",
        "label": "模型工具",
        "description": "模型服务、开发工具与 SDK",
        "hint": "模型服务 / 开发工具 / SDK",
    },
    {
        "id": "multimodal",
        "label": "多模态",
        "description": "视觉、语音与视频生成",
        "hint": "视觉理解 / 语音交互 / 视频生成",
    },
    {
        "id": "rag_data",
        "label": "RAG 与数据",
        "description": "检索、知识库与数据管线",
        "hint": "向量检索 / 知识库 / 数据管线",
    },
    {
        "id": "eval_safety",
        "label": "评测与安全",
        "description": "评测基准、对齐与安全护栏",
        "hint": "基准 / 对齐 / 安全护栏",
    },
    {
        "id": "open_models",
        "label": "开源模型",
        "description": "模型权重、微调与训练工具",
        "hint": "模型权重 / 微调 / 训练工具",
    },
    {
        "id": "ai_coding",
        "label": "AI 编程",
        "description": "编码 Agent、IDE 集成与代码评测",
        "hint": "编码 Agent / IDE 集成 / 代码评测",
    },
    {
        "id": "life",
        "label": "生活",
        "description": "家居、美食与日常消费",
        "hint": "家居 / 美食 / 城市生活",
    },
    {
        "id": "sports",
        "label": "运动",
        "description": "赛事、健身与户外运动",
        "hint": "足球 / 篮球 / 跑步健身",
    },
    {
        "id": "news",
        "label": "新闻",
        "description": "国际、社会与深度报道",
        "hint": "国际时事 / 国内社会 / 深度报道",
    },
    {
        "id": "finance",
        "label": "财经",
        "description": "市场、公司与宏观政策",
        "hint": "市场 / 公司 / 宏观政策",
    },
    {
        "id": "entertainment",
        "label": "娱乐",
        "description": "影视、音乐与综艺",
        "hint": "影视 / 音乐 / 综艺",
    },
    {
        "id": "science",
        "label": "科学",
        "description": "太空、生命科学与环境",
        "hint": "太空 / 生命科学 / 气候",
    },
    {
        "id": "health",
        "label": "健康",
        "description": "营养、运动康复与心理",
        "hint": "营养 / 康复 / 心理健康",
    },
    {
        "id": "auto",
        "label": "汽车",
        "description": "新能源、智能驾驶与新车",
        "hint": "新能源 / 智能驾驶 / 新车",
    },
    {
        "id": "travel",
        "label": "旅行",
        "description": "目的地、户外与城市漫游",
        "hint": "目的地 / 户外 / 城市漫游",
    },
    {
        "id": "education",
        "label": "教育",
        "description": "学习、升学与职业成长",
        "hint": "学习方法 / 升学 / 职业成长",
    },
    {
        "id": "games",
        "label": "游戏",
        "description": "新游、电竞与独立游戏",
        "hint": "新游 / 电竞 / 独立游戏",
    },
    {
        "id": "fashion",
        "label": "时尚",
        "description": "穿搭、美妆与设计",
        "hint": "穿搭 / 美妆 / 设计",
    },
]
TOPIC_LABELS = {item["label"] for item in TOPIC_PRESETS}
WINDOW_DAYS = {"day": 1, "week": 7}

CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
HTML_TAG = re.compile(r"<[^>]+>")


def clean_topic(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = HTML_TAG.sub("", value)
    value = CONTROL_CHARS.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


class RunCreate(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=3)
    window: Literal["day", "week"] = "week"
    mode: Literal["demo", "live"] = "demo"
    focus_keywords: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("topics")
    @classmethod
    def normalize_topics(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in values:
            topic = clean_topic(raw)
            if not topic:
                raise ValueError("话题不能为空")
            if len(topic) > 24:
                raise ValueError("单个话题不能超过 24 个字符")
            key = topic.casefold()
            if key not in seen:
                seen.add(key)
                cleaned.append(topic)
        if not cleaned:
            raise ValueError("至少需要一个话题")
        if len(cleaned) > 3:
            raise ValueError("单任务最多三个话题")
        return cleaned

    @field_validator("focus_keywords")
    @classmethod
    def normalize_focus_keywords(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in values or []:
            keyword = clean_topic(raw)
            if not keyword:
                continue
            if len(keyword) > 24:
                raise ValueError("单个细分兴趣不能超过 24 个字符")
            key = keyword.casefold()
            if key not in seen:
                seen.add(key)
                cleaned.append(keyword)
        if len(cleaned) > 3:
            raise ValueError("最多三个细分兴趣")
        return cleaned

    @model_validator(mode="after")
    def verify_preset_or_custom(self) -> "RunCreate":
        for topic in self.topics:
            if len(topic) < 2:
                raise ValueError("自定义话题至少需要 2 个字符")
        return self


class MarkReadRequest(BaseModel):
    event_ids: list[str] | None = None


# ---------- Structured model output schemas ----------


class QuerySpecLLM(BaseModel):
    text: str = Field(min_length=2, max_length=220)
    purpose: str = Field(min_length=2, max_length=220)
    strategy: Literal["open", "official", "specific"] = "open"
    topic: str = ""
    language: Literal["zh", "en", "mixed"] = "mixed"
    domains: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("text", "purpose")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @field_validator("domains")
    @classmethod
    def clean_domains(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            domain = value.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
            domain = domain.split("/")[0]
            if domain and re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
                cleaned.append(domain)
        return cleaned[:3]


class QueryPlanLLM(BaseModel):
    queries: list[QuerySpecLLM] = Field(min_length=1, max_length=6)
    notes: str = ""

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value: str) -> str:
        return (value or "")[:500]


class EvidenceLLM(BaseModel):
    document_id: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=2, max_length=600)


class FactLLM(BaseModel):
    statement: str = Field(min_length=2, max_length=500)
    category: str = "other"
    conditions: str = ""
    evidence: list[EvidenceLLM] = Field(min_length=1, max_length=3)

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        allowed = {
            "release",
            "performance",
            "compatibility",
            "api",
            "pricing",
            "availability",
            "research",
            "other",
        }
        value = (value or "other").lower()
        return value if value in allowed else "other"


class EventLLM(BaseModel):
    event_key: str = Field(min_length=2, max_length=160)
    title: str = Field(min_length=2, max_length=180)
    project: str = Field(default="", max_length=100)
    topic: str = Field(min_length=1, max_length=40)
    event_type: str = "release"
    event_date: str | None = None
    date_confidence: Literal["confirmed", "inferred", "unknown"] = "unknown"
    summary: str = Field(min_length=2, max_length=700)
    why_it_matters: str = Field(default="", max_length=500)
    confidence: Literal["high", "medium", "low"] = "medium"
    facts: list[FactLLM] = Field(default_factory=list, max_length=8)
    unresolved: list[str] = Field(default_factory=list, max_length=8)
    resolved_unresolved: list[str] = Field(default_factory=list, max_length=8)
    primary_document_id: str = ""

    @field_validator("event_type")
    @classmethod
    def known_event_type(cls, value: str) -> str:
        value = (value or "release").lower()
        allowed = {"release", "update", "research", "tool", "pricing", "compatibility", "other"}
        return value if value in allowed else "other"

    @field_validator("unresolved", "resolved_unresolved")
    @classmethod
    def trim_unresolved(cls, values: list[str]) -> list[str]:
        return [re.sub(r"\s+", " ", str(v)).strip()[:240] for v in values if str(v).strip()][:8]


class EventsLLM(BaseModel):
    events: list[EventLLM] = Field(default_factory=list, max_length=8)
    notes: str = ""


class GapQueryLLM(BaseModel):
    text: str = Field(min_length=2, max_length=220)
    purpose: str = Field(min_length=2, max_length=220)
    strategy: Literal["open", "official", "specific"] = "specific"
    domains: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("domains")
    @classmethod
    def clean_domains(cls, values: list[str]) -> list[str]:
        return QuerySpecLLM.clean_domains(values)


class GapLLM(BaseModel):
    reason_code: str = "other"
    description: str = Field(min_length=2, max_length=300)
    topic: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    query: GapQueryLLM | None = None


class GapAnalysisLLM(BaseModel):
    gaps: list[GapLLM] = Field(default_factory=list, max_length=4)
    notes: str = ""


def parse_event_date(value: Any, now: datetime) -> date | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in {"null", "none", "unknown", "未知"}:
        return None
    raw = raw.replace("年", "-").replace("月", "-").replace("日", "")
    raw = raw.replace("/", "-").replace(".", "-")
    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if not match:
        return None
    try:
        result = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
    if result > (now + timedelta(days=1)).date():
        return None
    return result


def window_bounds(window: str, now: datetime) -> tuple[datetime, datetime]:
    days = WINDOW_DAYS.get(window, 7)
    start = now - timedelta(days=days)
    return start, now


def event_in_window(event_date: date | None, window: str, now: datetime) -> bool | None:
    if event_date is None:
        return None
    start, end = window_bounds(window, now)
    return start.date() <= event_date <= end.date()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    # Microsecond precision keeps ordering stable when two local runs start in
    # the same second (important for new vs. updated event classification).
    return utc_now().isoformat(timespec="microseconds")
