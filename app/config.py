from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if value < minimum:
        raise ValueError(f"{name} 不能小于 {minimum}")
    return value


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if value < 0:
        raise ValueError(f"{name} 不能为负数")
    return value


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    db_path: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8790
    seed_demo_on_start: bool = True
    timezone: str = "Asia/Shanghai"

    # Per-run limits (configurable, defaults follow the product brief).
    max_searches: int = 8
    max_reads: int = 15
    max_model_calls: int = 9
    max_gap_rounds: int = 2
    max_seconds: int = 120

    # Optional daily caps. 0 means unlimited: usage is still recorded and shown.
    daily_search_budget: int = 0
    daily_read_budget: int = 0
    daily_model_budget: int = 0

    search_results_per_query: int = 5
    initial_query_limit: int = 5
    initial_read_limit: int = 9
    max_events: int = 5
    page_max_bytes: int = 2_000_000
    page_timeout_seconds: float = 18.0
    llm_timeout_seconds: float = 45.0
    demo_step_delay_seconds: float = 0.16

    # Search provider. "deepseek" uses the same key/base URL as the model;
    # "tavily" uses the dedicated Tavily search API.
    search_provider: str = "tavily"

    # Credentials. Never serialize these to API responses or logs.
    tavily_api_key: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.1
    llm_json_mode: bool = True
    llm_thinking: str = ""

    # Optional cost estimation. Zero means "not configured"; the UI shows usage
    # without inventing a monetary amount.
    tavily_cost_per_call_usd: float = 0.0
    llm_input_price_per_mtok_usd: float = 0.0
    llm_output_price_per_mtok_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.search_provider not in {"tavily", "deepseek"}:
            raise ValueError("SEARCH_PROVIDER 只支持 tavily 或 deepseek")
        if self.llm_thinking not in {"", "enabled", "disabled"}:
            raise ValueError("LLM_THINKING 只支持空值、enabled 或 disabled")

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("SIGNALFIELD_DATA_DIR", str(PROJECT_ROOT / "data")))
        db_path = Path(os.getenv("SIGNALFIELD_DB_PATH", "")) if os.getenv("SIGNALFIELD_DB_PATH") else None
        return cls(
            data_dir=data_dir,
            db_path=db_path,
            host=os.getenv("SIGNALFIELD_HOST", "127.0.0.1"),
            port=_env_int("SIGNALFIELD_PORT", 8790),
            seed_demo_on_start=os.getenv("SIGNALFIELD_SEED_DEMO", "true").lower()
            not in {"0", "false", "no"},
            timezone=os.getenv("SIGNALFIELD_TIMEZONE", "Asia/Shanghai"),
            max_searches=_env_int("MAX_SEARCHES", 8),
            max_reads=_env_int("MAX_READS", 15),
            max_model_calls=_env_int("MAX_MODEL_CALLS", 9),
            max_gap_rounds=_env_int("MAX_GAP_ROUNDS", 2, minimum=0),
            max_seconds=_env_int("MAX_SECONDS", 120),
            daily_search_budget=_env_int("DAILY_SEARCH_BUDGET", 0, minimum=0),
            daily_read_budget=_env_int("DAILY_READ_BUDGET", 0, minimum=0),
            daily_model_budget=_env_int("DAILY_MODEL_BUDGET", 0, minimum=0),
            search_results_per_query=_env_int("SEARCH_RESULTS_PER_QUERY", 5),
            initial_query_limit=_env_int("INITIAL_QUERY_LIMIT", 5),
            initial_read_limit=_env_int("INITIAL_READ_LIMIT", 9),
            max_events=_env_int("MAX_EVENTS", 5),
            page_max_bytes=_env_int("PAGE_MAX_BYTES", 2_000_000, minimum=10_000),
            page_timeout_seconds=_env_float("PAGE_TIMEOUT_SECONDS", 18.0),
            llm_timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 45.0),
            demo_step_delay_seconds=_env_float("DEMO_STEP_DELAY_SECONDS", 0.16),
            search_provider=os.getenv("SEARCH_PROVIDER", "tavily").strip().lower(),
            tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", "").strip(),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_model=os.getenv("LLM_MODEL", "").strip(),
            llm_temperature=_env_float("LLM_TEMPERATURE", 0.1),
            llm_json_mode=os.getenv("LLM_JSON_MODE", "true").lower() not in {"0", "false", "no"},
            llm_thinking=os.getenv("LLM_THINKING", "").strip().lower(),
            tavily_cost_per_call_usd=_env_float("TAVILY_COST_PER_CALL_USD", 0.0),
            llm_input_price_per_mtok_usd=_env_float("LLM_INPUT_PRICE_PER_MTOK_USD", 0.0),
            llm_output_price_per_mtok_usd=_env_float("LLM_OUTPUT_PRICE_PER_MTOK_USD", 0.0),
        )

    @property
    def resolved_db_path(self) -> Path:
        path = self.db_path or (self.data_dir / "signalfield.sqlite3")
        return path

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def search_provider_label(self) -> str:
        return "DeepSeek Search" if self.search_provider == "deepseek" else "Tavily"

    @property
    def live_missing(self) -> List[str]:
        mapping: dict[str, str] = {}
        if self.search_provider == "tavily":
            mapping["TAVILY_API_KEY"] = self.tavily_api_key
        mapping["LLM_BASE_URL"] = self.llm_base_url
        mapping["LLM_API_KEY"] = self.llm_api_key
        mapping["LLM_MODEL"] = self.llm_model
        return [name for name, value in mapping.items() if not value]

    @property
    def live_ready(self) -> bool:
        if self.search_provider not in {"tavily", "deepseek"}:
            return False
        return not self.live_missing

    @property
    def pricing_configured(self) -> bool:
        return any(
            value > 0
            for value in (
                self.tavily_cost_per_call_usd,
                self.llm_input_price_per_mtok_usd,
                self.llm_output_price_per_mtok_usd,
            )
        )

    @property
    def deepseek_search_url(self) -> str:
        base = self.llm_base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            base = base[: -len("/chat/completions")].rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/tools/search"
        return f"{base}/v1/tools/search"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_db_path.parent.mkdir(parents=True, exist_ok=True)

    def public_limits(self) -> dict:
        return {
            "searches": self.max_searches,
            "reads": self.max_reads,
            "model_calls": self.max_model_calls,
            "gap_rounds": self.max_gap_rounds,
            "seconds": self.max_seconds,
            "daily_searches": self.daily_search_budget,
            "daily_reads": self.daily_read_budget,
            "daily_model_calls": self.daily_model_budget,
        }
