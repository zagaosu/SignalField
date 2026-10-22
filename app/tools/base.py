from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ToolError(Exception):
    def __init__(self, message: str, *, transient: bool = False, code: str = "tool_error"):
        super().__init__(message)
        self.message = message
        self.transient = transient
        self.code = code


@dataclass
class QuerySpec:
    text: str
    purpose: str
    strategy: str
    topic: str
    language: str = "mixed"
    domains: list[str] = field(default_factory=list)
    round: int = 0
    gap_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "purpose": self.purpose,
            "strategy": self.strategy,
            "topic": self.topic,
            "language": self.language,
            "domains": list(self.domains),
            "round": self.round,
            "gap_id": self.gap_id,
        }


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    score: float = 0.0
    published_date: str | None = None
    domain: str = ""

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "score": self.score,
            "published_date": self.published_date,
            "domain": self.domain,
        }


@dataclass
class ReadResult:
    ok: bool
    url: str
    final_url: str = ""
    title: str = ""
    content: str = ""
    published_at: str | None = None
    language: str = ""
    error: str = ""
    content_type: str = ""
    byte_size: int = 0


class SearchTool:
    def search(self, spec: QuerySpec, *, window: str, limit: int) -> list[SearchHit]:
        raise NotImplementedError


class PageReader:
    def read(self, url: str, *, timeout_seconds: float | None = None) -> ReadResult:
        raise NotImplementedError


class LLMClient:
    def plan_queries(self, context: dict[str, Any]) -> tuple[dict, dict]:
        raise NotImplementedError

    def extract_events(self, context: dict[str, Any]) -> tuple[dict, dict]:
        raise NotImplementedError

    def analyze_gaps(self, context: dict[str, Any]) -> tuple[dict, dict]:
        raise NotImplementedError
