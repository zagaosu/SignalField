from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import PROJECT_ROOT, Settings
from .db import Repository, local_day
from .models import TOPIC_PRESETS, MarkReadRequest, RunCreate
from .services.runs import LiveConfigError, RunService
from .state import public_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
STATIC_DIR = PROJECT_ROOT / "app" / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    repo = Repository(settings.resolved_db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        repo.init()
        interrupted = repo.mark_interrupted_runs()
        if interrupted:
            logger.warning("Marked %s interrupted run(s) after restart", interrupted)
        service = RunService(settings, repo)
        app.state.repo = repo
        app.state.service = service
        app.state.settings = settings
        seed_id = service.seed_demo_if_needed()
        if seed_id:
            logger.info("Seeded demo run %s", seed_id)
        try:
            yield
        finally:
            service.shutdown()

    app = FastAPI(
        title="信号场 SignalField",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.repo = repo

    @app.middleware("http")
    async def secure_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        messages = []
        for error in exc.errors()[:4]:
            location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
            message = error.get("msg", "输入无效")
            messages.append(f"{location}: {message}" if location else message)
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "validation_error",
                    "message": "输入校验未通过：" + "；".join(messages),
                }
            },
        )

    def daily_usage() -> dict:
        day = local_day(settings.timezone)
        usage = repo.recent_usage(day)
        return {
            **usage,
            "day": day,
            "captured_at": datetime.now(settings.tz).isoformat(timespec="seconds"),
        }

    def detail_for(run_id: str) -> dict:
        row = repo.get_run_row(run_id)
        if not row:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "任务不存在"})
        events = repo.get_run_events(run_id)
        return public_state(
            row["state"],
            events=events,
            daily_usage=daily_usage(),
        )

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

    @app.get("/api/health")
    async def health():
        return {
            "ok": True,
            "version": __version__,
            "runs": len(repo.list_runs(limit=100)),
            "events": repo.event_count(),
        }

    @app.get("/api/config")
    async def config():
        usage = daily_usage()
        return {
            "version": __version__,
            "server_time": datetime.now(settings.tz).isoformat(timespec="seconds"),
            "timezone": settings.timezone,
            "topics": TOPIC_PRESETS,
            "windows": [
                {"value": "day", "label": "最近 24 小时"},
                {"value": "week", "label": "最近 7 天"},
            ],
            "search_provider": settings.search_provider,
            "search_provider_label": settings.search_provider_label,
            "modes": {
                "demo": {
                    "available": True,
                    "label": "演示样例",
                    "notice": "虚构语料；不执行实时搜索；不消耗远程额度；日期为样例日期。",
                },
                "live": {
                    "available": settings.live_ready,
                    "label": "真实检索",
                    "missing": settings.live_missing,
                    "provider": settings.search_provider,
                    "provider_label": settings.search_provider_label,
                    "model": settings.llm_model,
                    "notice": (
                        f"使用 {settings.search_provider_label} 与 "
                        f"{settings.llm_model or '模型服务'}；搜索结果摘要不作为证据。"
                    ),
                },
            },
            "limits": settings.public_limits(),
            "daily_usage": usage,
            "pricing_configured": settings.pricing_configured,
            "demo_notice": (
                "演示模式明确使用虚构样例；未执行实时搜索，不消耗远程调用额度；"
                "演示日期不代表真实事件日期。"
            ),
        }

    @app.post("/api/runs", status_code=202)
    async def create_run(payload: RunCreate):
        if payload.mode == "live" and not settings.live_ready:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "config_missing",
                    "message": "真实检索尚未配置完整，未静默回退到演示内容。",
                    "missing": settings.live_missing,
                },
            )
        try:
            state = app.state.service.create_and_start(payload)
        except LiveConfigError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "config_missing",
                    "message": str(exc),
                    "missing": exc.missing,
                },
            ) from exc
        return public_state(state, daily_usage=daily_usage())

    @app.get("/api/runs")
    async def list_runs(limit: int = 30):
        limit = max(1, min(limit, 100))
        return {"runs": repo.list_runs(limit=limit)}

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str):
        return detail_for(run_id)

    @app.post("/api/runs/{run_id}/cancel", status_code=202)
    async def cancel_run(run_id: str):
        if not app.state.service.cancel(run_id):
            row = repo.get_run_row(run_id)
            if not row:
                raise HTTPException(
                    status_code=404, detail={"code": "not_found", "message": "任务不存在"}
                )
            raise HTTPException(
                status_code=409,
                detail={"code": "not_cancellable", "message": "任务已经结束或不可取消"},
            )
        return {"ok": True, "status": "cancelling", "message": "已请求取消，将保留已完成的部分结果。"}

    @app.post("/api/runs/{run_id}/read")
    async def mark_run_read(run_id: str, _payload: MarkReadRequest | None = None):
        if not repo.get_run_row(run_id):
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "任务不存在"}
            )
        count = repo.mark_run_read(run_id)
        return {"ok": True, "marked": count}

    @app.post("/api/events/{event_id}/read")
    async def mark_event_read(event_id: str):
        if not repo.mark_event_read(event_id):
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "事件不存在"}
            )
        return {"ok": True, "event_id": event_id}

    @app.get("/api/updates")
    async def updates(limit: int = 20):
        items = repo.unread_updates(limit=max(1, min(limit, 100)))
        return {"count": len(items), "items": items}

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
