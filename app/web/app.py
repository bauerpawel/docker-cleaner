"""Panel WWW (FastAPI): lista nieużywanych obrazów, usuwanie, auto-czyszczenie."""

from __future__ import annotations

import logging
import os
import secrets
import sys
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .. import __version__
from ..cleaner import run_cleanup
from ..config import RuntimeConfig, save_runtime_config, validate_runtime
from ..docker_client import DockerClient, DockerUnavailableError
from ..scheduler import CleanupScheduler

logger = logging.getLogger("docker_cleaner.web")

BASE_DIR = os.path.dirname(__file__)
TEMPLATES = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


class DeleteRequest(BaseModel):
    ids: List[str] = Field(default_factory=list)
    force: bool = False


class SettingsUpdate(BaseModel):
    auto_clean: bool
    clean_scope: Literal["dangling", "all"]
    clean_build_cache: bool
    min_age: str
    clean_interval: str
    clean_cron: Optional[str] = None


def _make_auth_dependency(settings):
    """Zwraca dependency FastAPI: Basic Auth gdy skonfigurowane, inaczej brak."""
    if not settings.auth_enabled:
        def no_auth():
            return None
        return no_auth

    security = HTTPBasic()

    def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
        ok_user = secrets.compare_digest(credentials.username, settings.web_auth_user)
        ok_pass = secrets.compare_digest(credentials.password, settings.web_auth_password)
        if not (ok_user and ok_pass):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Nieprawidłowy login lub hasło",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    return require_auth


def _next_run_iso(scheduler: CleanupScheduler) -> Optional[str]:
    nxt = scheduler.next_run()
    return nxt.isoformat() if nxt else None


def _summarize_df(df: Optional[dict]) -> Optional[dict]:
    if not df:
        return None
    images = df.get("Images", []) or []
    total = sum(int(i.get("Size", 0) or 0) for i in images)
    reclaimable = sum(
        int(i.get("Size", 0) or 0) for i in images if int(i.get("Containers", 0) or 0) <= 0
    )
    return {
        "images_count": len(images),
        "images_total_bytes": total,
        "images_reclaimable_bytes": reclaimable,
    }


def create_app(settings, runtime: RuntimeConfig, docker_client=None) -> FastAPI:
    client = docker_client if docker_client is not None else DockerClient()
    auth = _make_auth_dependency(settings)

    # ``runtime`` to wspólny, mutowalny obiekt — zadanie zamyka się po nim,
    # więc aktualizacje z panelu są widoczne dla harmonogramu bez re-bindowania.
    def job() -> None:
        run_cleanup(client, runtime, data_dir=settings.data_dir)

    scheduler = CleanupScheduler(job, timezone=settings.tz)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if not client.ping():
            logger.warning(
                "Docker niedostępny przy starcie — panel wystartuje, ale operacje "
                "na obrazach będą zgłaszać błąd. Sprawdź montaż /var/run/docker.sock."
            )
        scheduler.start(runtime)
        yield
        scheduler.shutdown()

    app = FastAPI(title="Docker Cleaner", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.runtime = runtime
    app.state.scheduler = scheduler
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

    @app.exception_handler(DockerUnavailableError)
    async def _docker_unavailable(_request: Request, exc: DockerUnavailableError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, _user=Depends(auth)):
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {"auth_enabled": settings.auth_enabled},
        )

    @app.get("/api/images")
    def api_images(scope: Optional[str] = None, _user=Depends(auth)):
        chosen = scope if scope in ("dangling", "all") else runtime.clean_scope
        images = client.list_unused_images(chosen)
        images.sort(key=lambda i: i.get("size", 0), reverse=True)
        return {"scope": chosen, "count": len(images), "images": images}

    @app.post("/api/images/delete")
    def api_delete(req: DeleteRequest, _user=Depends(auth)):
        removed, errors = [], []
        for image_id in req.ids:
            try:
                client.remove_image(image_id, force=req.force)
                removed.append(image_id)
            except Exception as exc:  # noqa: BLE001
                errors.append({"id": image_id, "error": str(exc)})
        return {"removed": removed, "errors": errors}

    @app.post("/api/clean/run")
    def api_clean_run(_user=Depends(auth)):
        return run_cleanup(client, runtime, data_dir=settings.data_dir)

    @app.get("/api/settings")
    def api_get_settings(_user=Depends(auth)):
        return runtime.model_dump()

    @app.put("/api/settings")
    def api_put_settings(update: SettingsUpdate, _user=Depends(auth)):
        error = validate_runtime(update)
        if error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
        for key, value in update.model_dump().items():
            setattr(runtime, key, value)
        save_runtime_config(settings, runtime)
        scheduler.apply(runtime)
        return {
            "saved": True,
            "settings": runtime.model_dump(),
            "next_run": _next_run_iso(scheduler),
        }

    @app.get("/api/status")
    def api_status(_user=Depends(auth)):
        try:
            df = client.disk_usage()
        except Exception:  # noqa: BLE001
            df = None
        return {
            "auto_clean": runtime.auto_clean,
            "scope": runtime.clean_scope,
            "next_run": _next_run_iso(scheduler),
            "disk": _summarize_df(df),
        }

    @app.get("/healthz")
    def healthz():
        try:
            docker_ok = client.ping()
        except Exception:  # noqa: BLE001
            docker_ok = False
        return {"status": "ok", "docker": docker_ok}

    return app


def run_web(settings, runtime: RuntimeConfig) -> None:
    if settings.auth_misconfigured:
        logger.error(
            "WEB_AUTH_ENABLED=true, ale brakuje WEB_AUTH_USER/WEB_AUTH_PASSWORD — "
            "panel byłby otwarty mimo żądania logowania. Ustaw login i hasło."
        )
        sys.exit(2)

    app = create_app(settings, runtime)
    logger.info(
        "Panel WWW na porcie %d (auth=%s, auto_clean=%s)",
        settings.web_port,
        settings.auth_enabled,
        runtime.auto_clean,
    )
    uvicorn.run(app, host="0.0.0.0", port=settings.web_port, log_level="info")
