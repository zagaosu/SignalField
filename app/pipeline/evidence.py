from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

VERSION_RE = re.compile(r"\b\d+(?:\.\d+){1,3}\b")
PERFORMANCE_HINTS = re.compile(
    r"(提升|降低|加速|减少|吞吐|延迟|性能|快 \d|慢 \d|speedup|latency|throughput|%|倍|x faster)",
    re.I,
)
CONFLICT_HINTS = ("冲突", "不一致", "矛盾", "conflict", "inconsistent")
OFFICIAL_HINTS = ("官方", "official", "release", "docs", "github", "changelog", "blog")


def normalize_ws(value: str) -> str:
    """Whitespace cleanup for display and storage; punctuation is preserved."""
    value = str(value or "")
    value = value.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", value).strip()


def _normalize_for_match(value: str) -> str:
    """Only whitespace/width normalization is used for quote matching."""
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", "", value)


def quote_verified(quote: str, content: str) -> bool:
    quote_n = _normalize_for_match(quote)
    content_n = _normalize_for_match(content)
    if len(quote_n) < 4:
        return False
    return quote_n in content_n


def content_hash(content: str) -> str:
    return hashlib.sha1(normalize_ws(content).encode("utf-8")).hexdigest()


def text_similarity(a: str, b: str) -> float:
    left = normalize_ws(a)[:5000]
    right = normalize_ws(b)[:5000]
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left[:2500], right[:2500], autojunk=False).ratio()


def shingle_jaccard(a: str, b: str, width: int = 4) -> float:
    left = re.sub(r"\s+", "", normalize_ws(a))[:6000]
    right = re.sub(r"\s+", "", normalize_ws(b))[:6000]
    if len(left) < width or len(right) < width:
        return 0.0
    sa = {left[i : i + width] for i in range(len(left) - width + 1)}
    sb = {right[i : i + width] for i in range(len(right) - width + 1)}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def is_near_duplicate(doc: dict, previous: list[dict]) -> str | None:
    digest = doc.get("content_hash")
    for other in previous:
        if not other.get("content") or other.get("read_status") != "success":
            continue
        if digest and other.get("content_hash") == digest:
            return other["id"]
        if doc.get("title") and other.get("title"):
            title_sim = SequenceMatcher(
                None, normalize_ws(doc["title"]).lower(), normalize_ws(other["title"]).lower()
            ).ratio()
            body_sim = shingle_jaccard(doc.get("content", ""), other.get("content", ""))
            if title_sim >= 0.87 or body_sim >= 0.82:
                return other["id"]
    return None


def normalize_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower().strip()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value).strip("-")[:160]


def versions_in(text: str) -> set[str]:
    return set(VERSION_RE.findall(text or ""))


def same_event(left: dict, right: dict) -> bool:
    if normalize_key(left.get("event_key", "")) == normalize_key(right.get("event_key", "")):
        return True
    if left.get("project") and right.get("project"):
        project_l = normalize_key(left["project"])
        project_r = normalize_key(right["project"])
        if project_l == project_r:
            versions_l = versions_in(f"{left.get('title','')} {left.get('event_key','')}")
            versions_r = versions_in(f"{right.get('title','')} {right.get('event_key','')}")
            if versions_l and versions_r and versions_l & versions_r:
                return True
            if (
                left.get("event_type") == right.get("event_type")
                and left.get("event_date")
                and right.get("event_date")
                and left["event_date"] == right["event_date"]
                and title_similarity(left.get("title", ""), right.get("title", "")) >= 0.68
            ):
                return True
    return title_similarity(left.get("title", ""), right.get("title", "")) >= 0.9


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_ws(a).lower(), normalize_ws(b).lower()).ratio()


def merge_event(target: dict, incoming: dict) -> dict:
    if not target:
        return incoming
    target_facts = {_fact_key(f): f for f in target.get("facts", [])}
    for fact in incoming.get("facts", []):
        key = _fact_key(fact)
        existing = target_facts.get(key)
        if existing is None:
            # A later primary source can add missing benchmark conditions to
            # the same claim without creating a duplicate fact row.
            statement_key = re.sub(
                r"[^a-z0-9\u4e00-\u9fff]+",
                "",
                normalize_ws(fact.get("statement", "")).lower(),
            )
            for candidate in target.get("facts", []):
                candidate_key = re.sub(
                    r"[^a-z0-9\u4e00-\u9fff]+",
                    "",
                    normalize_ws(candidate.get("statement", "")).lower(),
                )
                if candidate_key == statement_key:
                    existing = candidate
                    break
        if existing is not None:
            if not normalize_ws(existing.get("conditions")) and normalize_ws(fact.get("conditions")):
                existing["conditions"] = normalize_ws(fact.get("conditions"))
            seen = {(e.get("document_id"), normalize_ws(e.get("quote", ""))) for e in existing["evidence"]}
            for evidence in fact.get("evidence", []):
                marker = (evidence.get("document_id"), normalize_ws(evidence.get("quote", "")))
                if marker not in seen:
                    existing["evidence"].append(evidence)
                    seen.add(marker)
            target_facts[_fact_key(existing)] = existing
        else:
            target["facts"].append(fact)
            target_facts[key] = fact
    unresolved = list(target.get("unresolved", []))
    for resolved in incoming.get("resolved_unresolved", []):
        unresolved = [
            item for item in unresolved if normalize_ws(item) != normalize_ws(resolved)
        ]
    for item in incoming.get("unresolved", []):
        if item not in unresolved:
            unresolved.append(item)
    target["unresolved"] = unresolved[:10]
    summary_should_refresh = bool(
        incoming.get("resolved_unresolved")
        or (not target.get("event_date") and incoming.get("event_date"))
        or (target.get("date_conflict") and not incoming.get("date_conflict"))
    )
    if summary_should_refresh and incoming.get("summary"):
        target["summary"] = incoming["summary"]
    docs = {d.get("document_id") or d.get("id") for d in target.get("sources", [])}
    for source in incoming.get("sources", []):
        if (source.get("document_id") or source.get("id")) not in docs:
            target.setdefault("sources", []).append(source)
    target["date_conflict"] = bool(target.get("date_conflict") or incoming.get("date_conflict"))
    date_l = target.get("event_date")
    date_r = incoming.get("event_date")
    if date_l and date_r and date_l != date_r:
        diff = abs((date.fromisoformat(date_l) - date.fromisoformat(date_r)).days)
        if diff >= 1:
            target["date_conflict"] = True
            note = f"来源显示的事件日期存在冲突：{date_l} / {date_r}"
            if note not in target["unresolved"]:
                target["unresolved"].append(note)
    confidence_rank = {"unknown": 0, "inferred": 1, "confirmed": 2}
    if confidence_rank.get(incoming.get("date_confidence"), 0) > confidence_rank.get(
        target.get("date_confidence"), 0
    ):
        target["event_date"] = incoming.get("event_date") or target.get("event_date")
        target["date_confidence"] = incoming.get("date_confidence", target.get("date_confidence"))
    if incoming.get("confidence_score", 0) > target.get("confidence_score", 0):
        target["confidence_score"] = incoming["confidence_score"]
        target["confidence"] = incoming.get("confidence", target.get("confidence"))
    if not target.get("why_it_matters") and incoming.get("why_it_matters"):
        target["why_it_matters"] = incoming["why_it_matters"]
    if not target.get("primary_document_id") and incoming.get("primary_document_id"):
        target["primary_document_id"] = incoming["primary_document_id"]
    _recompute_sources(target)
    return target


def _fact_key(fact: dict) -> str:
    return re.sub(
        r"[^a-z0-9\u4e00-\u9fff]+",
        "",
        f"{fact.get('statement','')}{fact.get('conditions','')}".lower(),
    )


def _recompute_sources(event: dict) -> None:
    sources = []
    seen = set()
    for source in event.get("sources", []):
        doc_id = source.get("document_id") or source.get("id")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        sources.append(source)
    domains = {s.get("domain") for s in sources if s.get("domain")}
    event["sources"] = sources
    event["source_count"] = len(sources)
    event["source_domains"] = sorted(domains)
    event["independent_source_count"] = len(domains)
    event["primary_document_id"] = event.get("primary_document_id") or (
        sources[0].get("document_id") if sources else ""
    )


def document_priority(doc: dict, query_by_id: dict[str, dict]) -> float:
    score = float(doc.get("search_score") or 0)
    query = query_by_id.get((doc.get("query_ids") or [""])[0], {})
    strategy = query.get("strategy", "open")
    if strategy == "official":
        score += 0.35
    elif strategy == "specific":
        score += 0.15
    if doc.get("published_at"):
        score += 0.08
    score += min(len(doc.get("snippet", "")) / 1200, 0.12)
    return score


def recency_score(event_date: str | None, now: datetime, window: str) -> float:
    if not event_date:
        return 0.35
    try:
        days = (now.date() - date.fromisoformat(event_date)).days
    except ValueError:
        return 0.35
    horizon = 1 if window == "day" else 7
    return max(0.2, 1 - max(0, days) / (horizon + 1))


def event_score(event: dict, now: datetime, window: str, max_sources: int = 3) -> float:
    supported = [f for f in event.get("facts", []) if f.get("status") == "supported"]
    evidence_count = sum(len(f.get("evidence", [])) for f in supported)
    source_score = min(1.0, event.get("independent_source_count", 0) / max_sources)
    evidence_score = min(1.0, evidence_count / 4)
    date_score = {"confirmed": 1.0, "inferred": 0.65, "unknown": 0.3}.get(
        event.get("date_confidence"), 0.3
    )
    confidence = float(event.get("confidence_score") or 0.5)
    score = (
        0.32 * recency_score(event.get("event_date"), now, window)
        + 0.27 * evidence_score
        + 0.16 * source_score
        + 0.15 * date_score
        + 0.10 * confidence
    )
    if event.get("date_conflict"):
        score -= 0.12
    return round(max(0.0, min(1.0, score)), 4)


def fact_has_missing_conditions(fact: dict) -> bool:
    if fact.get("category") != "performance":
        return False
    statement = fact.get("statement", "")
    return bool(PERFORMANCE_HINTS.search(statement)) and not normalize_ws(fact.get("conditions", ""))


def contains_conflict(items: list[str]) -> bool:
    return any(any(hint in item.lower() for hint in CONFLICT_HINTS) for item in items)


def event_too_old(event_date: date | None, start: datetime, end: datetime) -> bool:
    if event_date is None:
        return False
    return not (start.date() <= event_date <= end.date())


def evidence_stats(facts: list[dict]) -> dict[str, Any]:
    total = len(facts)
    supported = sum(1 for f in facts if f.get("status") == "supported")
    evidence_total = sum(len(f.get("evidence", [])) for f in facts)
    evidence_verified = sum(
        1 for f in facts for e in f.get("evidence", []) if e.get("verified")
    )
    return {
        "facts_total": total,
        "facts_supported": supported,
        "evidence_total": evidence_total,
        "evidence_verified": evidence_verified,
    }
