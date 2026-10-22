from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import iso_now

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    topics TEXT NOT NULL,
    window TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT,
    stop_reason TEXT,
    stop_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    progress INTEGER NOT NULL DEFAULT 0,
    card_count INTEGER NOT NULL DEFAULT 0,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    event_date TEXT,
    date_confidence TEXT,
    change_type TEXT NOT NULL,
    change_note TEXT,
    fact_fingerprint TEXT,
    fact_keys_json TEXT,
    source_count INTEGER NOT NULL DEFAULT 0,
    independent_source_count INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0,
    read_at TEXT,
    payload_json TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, event_key)
);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, position);
CREATE INDEX IF NOT EXISTS idx_events_key ON events(event_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_unread ON events(read_at, change_type);

CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    units INTEGER NOT NULL DEFAULT 1,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    simulated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_day ON usage(day, kind, simulated);
"""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _event_id(run_id: str, event_key: str) -> str:
    digest = hashlib.sha1(f"{run_id}:{event_key}".encode("utf-8")).hexdigest()[:12]
    return f"evt_{digest}"


def _storage_state(state: dict) -> dict:
    """Strip full page text before persistence.

    Full content is kept in memory only for the duration of a run. SQLite keeps
    source metadata, a short excerpt and the exact evidence quotes needed for
    auditability. This limits local caching of third-party pages.
    """
    data = copy.deepcopy(state)
    for key in [key for key in data if str(key).startswith("_")]:
        data.pop(key, None)
    for document in data.get("documents", []):
        content = document.pop("content", "")
        if content and not document.get("content_excerpt"):
            document["content_excerpt"] = content[:1200]
        excerpt = document.get("content_excerpt") or ""
        document["content_excerpt"] = excerpt[:1200]
    return data


class Repository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._write_lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=12, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=12000")
        return conn

    @contextmanager
    def connection(self):
        """Commit on success and always close (important on Windows)."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._write_lock, self.connection() as conn:
            conn.executescript(SCHEMA)

    def has_runs(self) -> bool:
        with self.connection() as conn:
            return conn.execute("SELECT 1 FROM runs LIMIT 1").fetchone() is not None

    def create_run(self, state: dict) -> None:
        now = iso_now()
        with self._write_lock, self.connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, mode, topics, window, status, stage, created_at,
                                  progress, card_count, state_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state["id"],
                    state["mode"],
                    _json(state["topics"]),
                    state["window"],
                    state["status"],
                    state.get("stage"),
                    state["created_at"],
                    state.get("progress", {}).get("percent", 0),
                    0,
                    _json(state),
                    now,
                ),
            )

    def save_state(self, state: dict) -> None:
        now = iso_now()
        progress = state.get("progress", {}).get("percent", 0)
        storage = _storage_state(state)
        with self._write_lock, self.connection() as conn:
            conn.execute(
                """
                UPDATE runs SET status=?, stage=?, stop_reason=?, stop_message=?,
                    started_at=?, finished_at=?, progress=?, card_count=?, state_json=?,
                    updated_at=?
                WHERE id=?
                """,
                (
                    state["status"],
                    state.get("stage"),
                    state.get("stop_reason"),
                    state.get("stop_message"),
                    state.get("started_at"),
                    state.get("finished_at"),
                    progress,
                    len(state.get("events", [])),
                    _json(storage),
                    now,
                    state["id"],
                ),
            )

    def set_cancelling(self, run_id: str) -> bool:
        with self._write_lock, self.connection() as conn:
            row = conn.execute(
                "SELECT state_json, status FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if not row:
                return False
            if row["status"] not in {"queued", "running"}:
                return False
            state = _loads(row["state_json"], {})
            state["cancel_requested"] = True
            state["status"] = "cancelling"
            state["stop_message"] = "正在取消，已完成的检索结果会被保留。"
            conn.execute(
                "UPDATE runs SET status=?, stop_message=?, state_json=?, updated_at=? WHERE id=?",
                ("cancelling", state["stop_message"], _json(state), iso_now(), run_id),
            )
            return True

    def get_run_row(self, run_id: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["topics"] = _loads(result["topics"], [])
        result["state"] = _loads(result["state_json"], {})
        return result

    def get_state(self, run_id: str) -> dict | None:
        row = self.get_run_row(run_id)
        return row["state"] if row else None

    def list_runs(self, limit: int = 30) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT r.id, r.mode, r.topics, r.window, r.status, r.stage,
                       r.stop_reason, r.stop_message, r.created_at, r.started_at,
                       r.finished_at, r.progress, r.card_count,
                       COALESCE(SUM(CASE WHEN e.read_at IS NULL
                           AND e.change_type IN ('new','updated') THEN 1 ELSE 0 END), 0) AS unread
                FROM runs r LEFT JOIN events e ON e.run_id = r.id
                GROUP BY r.id
                ORDER BY r.created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["topics"] = _loads(item["topics"], [])
            result.append(item)
        return result

    def recent_usage(self, day: str) -> dict:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT kind, SUM(units) AS units, SUM(tokens_in) AS tokens_in,
                       SUM(tokens_out) AS tokens_out, SUM(cost_usd) AS cost_usd
                FROM usage WHERE day=? AND simulated=0 GROUP BY kind
                """,
                (day,),
            ).fetchall()
        result = {
            "search_calls": 0,
            "read_calls": 0,
            "model_calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
        }
        keymap = {"search": "search_calls", "read": "read_calls", "model": "model_calls"}
        for row in rows:
            key = keymap.get(row["kind"])
            if key:
                result[key] = int(row["units"] or 0)
            result["tokens_in"] += int(row["tokens_in"] or 0)
            result["tokens_out"] += int(row["tokens_out"] or 0)
            result["cost_usd"] += float(row["cost_usd"] or 0)
        return result

    def record_usage(
        self,
        day: str,
        run_id: str,
        kind: str,
        units: int = 1,
        simulated: bool = False,
    ) -> int:
        with self._write_lock, self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO usage (day, run_id, kind, units, simulated, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (day, run_id, kind, units, 1 if simulated else 0, iso_now()),
            )
            return int(cursor.lastrowid)

    def update_usage_tokens(
        self, usage_id: int, tokens_in: int, tokens_out: int, cost: float
    ) -> None:
        with self._write_lock, self.connection() as conn:
            conn.execute(
                "UPDATE usage SET tokens_in=?, tokens_out=?, cost_usd=? WHERE id=?",
                (max(0, tokens_in), max(0, tokens_out), max(0.0, cost), usage_id),
            )

    def mark_interrupted_runs(self) -> int:
        now = iso_now()
        changed = 0
        with self._write_lock, self.connection() as conn:
            rows = conn.execute(
                "SELECT id, state_json, status FROM runs WHERE status IN ('queued','running','cancelling')"
            ).fetchall()
            for row in rows:
                state = _loads(row["state_json"], {})
                state["status"] = "cancelled" if row["status"] == "cancelling" else "partial"
                state["stop_reason"] = "server_restart"
                state["stop_message"] = "本地服务重启，任务已中断；已保存的部分结果仍然可以查看。"
                state["finished_at"] = now
                state["warnings"] = list(state.get("warnings", [])) + [state["stop_message"]]
                state["progress"] = {
                    "percent": 100,
                    "stage": "done",
                    "message": "任务已中断",
                }
                conn.execute(
                    """
                    UPDATE runs SET status=?, stop_reason=?, stop_message=?, finished_at=?,
                        progress=100, state_json=?, updated_at=? WHERE id=?
                    """,
                    (
                        state["status"],
                        "server_restart",
                        state["stop_message"],
                        now,
                        _json(state),
                        now,
                        row["id"],
                    ),
                )
                changed += 1
        return changed

    def persist_events(self, state: dict) -> list[dict]:
        """Store ranked events and compute substantive-update status."""
        now = iso_now()
        created_at = state.get("created_at", now)
        mode = state["mode"]
        stored: list[dict] = []
        with self._write_lock, self.connection() as conn:
            for position, event in enumerate(state.get("events", [])):
                prior = conn.execute(
                    """
                    SELECT e.* FROM events e JOIN runs r ON r.id=e.run_id
                    WHERE e.event_key=? AND r.mode=? AND r.created_at < ?
                    ORDER BY r.created_at DESC LIMIT 1
                    """,
                    (event["event_key"], mode, created_at),
                ).fetchone()
                event_id = event.get("id") or _event_id(state["id"], event["event_key"])
                fact_keys = sorted(
                    {
                        _normalize_fact_key(f.get("statement", ""), f.get("conditions", ""))
                        for f in event.get("facts", [])
                        if f.get("status") == "supported"
                    }
                )
                fingerprint = hashlib.sha1("\n".join(fact_keys).encode("utf-8")).hexdigest()
                change_type = "new"
                change_note = "首次收录"
                if prior:
                    prior_keys = set(_loads(prior["fact_keys_json"], []))
                    new_keys = set(fact_keys) - prior_keys
                    prior_date = prior["event_date"]
                    date_changed = (not prior_date) and bool(event.get("event_date"))
                    if new_keys or date_changed:
                        change_type = "updated"
                        bits = []
                        if new_keys:
                            bits.append(f"新增 {len(new_keys)} 条有证据事实")
                        if date_changed:
                            bits.append("补齐事件日期")
                        change_note = "；".join(bits)
                    else:
                        change_type = "unchanged"
                        change_note = "与历史记录相比无实质更新"
                event["id"] = event_id
                event["change_type"] = change_type
                event["change_note"] = change_note
                event["fact_fingerprint"] = fingerprint
                read_at = now if change_type == "unchanged" else None
                event["read_at"] = read_at
                payload = dict(event)
                conn.execute(
                    """
                    INSERT INTO events (
                        id, run_id, event_key, topic, title, summary, event_date,
                        date_confidence, change_type, change_note, fact_fingerprint,
                        fact_keys_json, source_count, independent_source_count,
                        confidence, read_at, payload_json, position, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        state["id"],
                        event["event_key"],
                        event.get("topic", ""),
                        event.get("title", ""),
                        event.get("summary", ""),
                        event.get("event_date"),
                        event.get("date_confidence", "unknown"),
                        change_type,
                        change_note,
                        fingerprint,
                        _json(fact_keys),
                        int(event.get("source_count", 0)),
                        int(event.get("independent_source_count", 0)),
                        float(event.get("confidence_score", 0)),
                        read_at,
                        _json(payload),
                        position,
                        now,
                    ),
                )
                stored.append(payload)
            conn.execute(
                "UPDATE runs SET card_count=?, updated_at=? WHERE id=?",
                (len(stored), now, state["id"]),
            )
        return stored

    def get_run_events(self, run_id: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id, read_at, change_type, change_note, payload_json FROM events WHERE run_id=? ORDER BY position",
                (run_id,),
            ).fetchall()
        events = []
        for row in rows:
            payload = _loads(row["payload_json"], {})
            payload["id"] = row["id"]
            payload["read_at"] = row["read_at"]
            payload["change_type"] = row["change_type"]
            payload["change_note"] = row["change_note"]
            events.append(payload)
        return events

    def mark_event_read(self, event_id: str) -> bool:
        with self._write_lock, self.connection() as conn:
            cursor = conn.execute(
                "UPDATE events SET read_at=COALESCE(read_at, ?) WHERE id=?",
                (iso_now(), event_id),
            )
            return cursor.rowcount > 0

    def mark_run_read(self, run_id: str) -> int:
        with self._write_lock, self.connection() as conn:
            cursor = conn.execute(
                "UPDATE events SET read_at=COALESCE(read_at, ?) WHERE run_id=?",
                (iso_now(), run_id),
            )
            return cursor.rowcount

    def unread_updates(self, limit: int = 20) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT e.id, e.run_id, e.event_key, e.topic, e.title, e.summary,
                       e.event_date, e.change_type, e.change_note, e.created_at,
                       r.mode
                FROM events e JOIN runs r ON r.id=e.run_id
                WHERE e.read_at IS NULL AND e.change_type IN ('new','updated')
                ORDER BY e.created_at DESC LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def event_count(self) -> int:
        with self.connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])


def _normalize_fact_key(statement: str, conditions: str) -> str:
    text = f"{statement}|{conditions}".lower()
    return "".join(ch for ch in text if ch.isalnum())


def local_day(timezone_name: str = "Asia/Shanghai") -> str:
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).date().isoformat()
