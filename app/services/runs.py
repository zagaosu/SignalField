from __future__ import annotations

import logging
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from ..config import Settings
from ..db import Repository
from ..demo import build_demo_bundle
from ..llm.openai_compatible import OpenAICompatibleLLM
from ..models import RunCreate, iso_now
from ..pipeline.orchestrator import AgentPipeline
from ..state import new_state
from ..tools.reader import SafePageReader
from ..tools.search import DeepSeekSearchTool, TavilySearchTool

logger = logging.getLogger(__name__)


class LiveConfigError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("真实检索需要服务端配置：" + "、".join(missing))


class RunService:
    def __init__(self, settings: Settings, repo: Repository):
        self.settings = settings
        self.repo = repo
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="signalfield-run")
        self._active: dict[str, dict] = {}
        self._lock = threading.RLock()

    def new_run_id(self) -> str:
        return "run_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(3)

    def create_and_start(self, payload: RunCreate) -> dict:
        if payload.mode == "live" and not self.settings.live_ready:
            raise LiveConfigError(self.settings.live_missing)
        run_id = self.new_run_id()
        state = new_state(
            run_id=run_id,
            mode=payload.mode,
            topics=payload.topics,
            window=payload.window,
            settings=self.settings,
            focus_keywords=payload.focus_keywords,
        )
        self.repo.create_run(state)
        ctx = {"cancel_event": threading.Event(), "state": state}
        with self._lock:
            self._active[run_id] = ctx
        try:
            self._executor.submit(self._execute, state, ctx["cancel_event"])
        except Exception:
            logger.exception("Failed to schedule run %s", run_id)
            state["status"] = "failed"
            state["stop_reason"] = "internal_error"
            state["stop_message"] = "任务调度失败。"
            self.repo.save_state(state)
            with self._lock:
                self._active.pop(run_id, None)
            raise
        return state

    def _execute(self, state: dict, cancel_event: threading.Event) -> None:
        run_id = state["id"]
        search_tool = reader = llm = None
        try:
            now = datetime.now(self.settings.tz)
            if state["mode"] == "demo":
                search_tool, reader, llm, _corpus = build_demo_bundle(now)
                delay = self.settings.demo_step_delay_seconds
            else:
                if not self.settings.live_ready:
                    raise LiveConfigError(self.settings.live_missing)
                if self.settings.search_provider == "deepseek":
                    search_tool = DeepSeekSearchTool(self.settings)
                else:
                    search_tool = TavilySearchTool(self.settings)
                reader = SafePageReader(self.settings)
                llm = OpenAICompatibleLLM(self.settings)
                delay = 0.0
            pipeline = AgentPipeline(
                settings=self.settings,
                repo=self.repo,
                search_tool=search_tool,
                reader=reader,
                llm=llm,
                cancel_event=cancel_event,
                now=now,
                delay_seconds=delay,
            )
            pipeline.run(state)
            if state.get("status") in {"queued", "running", "cancelling"}:
                state["status"] = "failed"
                state["stop_reason"] = "internal_error"
                state["stop_message"] = "任务未进入终态，已标记失败；请查看运行记录。"
                state["finished_at"] = iso_now()
                self.repo.save_state(state)
        except LiveConfigError as exc:
            state["status"] = "failed"
            state["stop_reason"] = "config_missing"
            state["stop_message"] = str(exc)
            state["finished_at"] = iso_now()
            self.repo.save_state(state)
        except Exception:
            logger.exception("Unhandled run failure for %s", run_id)
            if state.get("status") not in {"completed", "partial", "failed", "cancelled"}:
                state["status"] = "failed"
                state["stop_reason"] = "internal_error"
                state["stop_message"] = "任务执行失败，请稍后重试。"
                self.repo.save_state(state)
        finally:
            for tool in (search_tool, reader, llm):
                try:
                    if tool is not None:
                        tool.close()
                except Exception:
                    pass
            with self._lock:
                self._active.pop(run_id, None)

    def cancel(self, run_id: str) -> bool:
        with self._lock:
            ctx = self._active.get(run_id)
            if not ctx:
                return False
            state = ctx["state"]
            if state.get("status") not in {"queued", "running", "cancelling"}:
                return False
            ctx["cancel_event"].set()
            state["cancel_requested"] = True
            state["status"] = "cancelling"
            state["stop_message"] = "正在取消，已完成的检索结果会被保留。"
            self.repo.save_state(state)
        return True

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def seed_demo_if_needed(self) -> str | None:
        if not self.settings.seed_demo_on_start or self.repo.has_runs():
            return None
        payload = RunCreate(
            topics=["Agent", "推理部署", "模型工具"],
            window="week",
            mode="demo",
        )
        run_id = "run_seed_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        state = new_state(
            run_id=run_id,
            mode="demo",
            topics=payload.topics,
            window=payload.window,
            settings=self.settings,
        )
        self.repo.create_run(state)
        now = datetime.now(self.settings.tz)
        search_tool, reader, llm, _corpus = build_demo_bundle(now)
        try:
            pipeline = AgentPipeline(
                settings=self.settings,
                repo=self.repo,
                search_tool=search_tool,
                reader=reader,
                llm=llm,
                cancel_event=threading.Event(),
                now=now,
                delay_seconds=0.0,
            )
            pipeline.run(state)
            # Seeded events remain unread so the update / mark-read interaction
            # is visible on first launch; opening a card marks it read.
        except Exception:
            logger.exception("Demo seed failed")
            return None
        return run_id
