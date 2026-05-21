"""FastAPI application entry point for the backend scaffold."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import asynccontextmanager
from importlib import import_module

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from server.core.chroma import get_chroma_client
from server.core.config import get_settings
from server.core.database import get_engine, get_session_factory
from server.core.exceptions import CoreError, InfrastructureUnavailableError
from server.core.llm import get_llm_client
from server.db.metadata import import_model_modules
from server.modules.auth.service import bootstrap_admin_if_configured

MODULE_ROUTER_PATHS = (
    "server.modules.documents.router",
    "server.modules.auth.router",
    "server.modules.synthesis.router",
    "server.modules.evaluations.router",
    "server.modules.feedback.router",
    "server.modules.admin.router",
)


def _load_module_routers() -> Iterable[APIRouter]:
    for path in MODULE_ROUTER_PATHS:
        try:
            module = import_module(path)
        except ModuleNotFoundError as exc:
            if exc.name == path:
                continue
            raise

        router = getattr(module, "router", None)
        if router is not None:
            yield router


def _probe_runtime_dependency(name: str, loader: callable) -> tuple[bool, str]:
    try:
        loader()
    except CoreError as exc:
        return False, str(exc)
    except Exception as exc:  # pragma: no cover - defensive guard
        return False, f"Unexpected error: {exc}"
    return True, "ok"


def _bootstrap_admin_if_needed() -> None:
    settings = get_settings()
    if not settings.database_configured:
        return

    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        bootstrap_admin_if_configured(session, settings)
    except Exception as exc:  # pragma: no cover - startup guard
        raise InfrastructureUnavailableError(
            "Initial admin bootstrap could not be completed"
        ) from exc
    finally:
        session.close()


def create_app() -> FastAPI:
    settings = get_settings()
    import_model_modules()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _bootstrap_admin_if_needed()
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    api_router = APIRouter(prefix=settings.api_prefix)
    for router in _load_module_routers():
        api_router.include_router(router)

    @api_router.get("/")
    def api_root() -> dict[str, str]:
        return {"service": settings.app_name, "version": settings.app_version}

    app.include_router(api_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", response_model=None)
    def ready() -> JSONResponse | dict[str, object]:
        checks: dict[str, dict[str, object]] = {
            "database": {
                "configured": settings.database_configured,
                "ready": False,
                "detail": "DATABASE_URL is not configured",
            },
            "chroma": {
                "configured": settings.chroma_configured,
                "ready": False,
                "detail": "Chroma settings are not configured",
            },
            "llm": {
                "configured": settings.llm_configured,
                "ready": False,
                "detail": "ANTHROPIC_API_KEY is not configured",
            },
            "embedding": {
                "configured": settings.embedding_configured,
                "ready": settings.embedding_configured,
                "detail": "lazy load deferred until first embedding request",
            },
        }

        if settings.database_configured:
            ok, detail = _probe_runtime_dependency("database", get_engine)
            checks["database"] = {"configured": True, "ready": ok, "detail": detail}

        if settings.chroma_configured:
            ok, detail = _probe_runtime_dependency("chroma", get_chroma_client)
            checks["chroma"] = {"configured": True, "ready": ok, "detail": detail}

        if settings.llm_configured:
            ok, detail = _probe_runtime_dependency("llm", get_llm_client)
            checks["llm"] = {"configured": True, "ready": ok, "detail": detail}

        ready = all(check["ready"] for check in checks.values())
        payload = {
            "status": "ready" if ready else "not_ready",
            "checks": checks,
            "notes": {
                "embedding": (
                    "Embedding model loading is intentionally deferred to "
                    "avoid heavy startup work."
                )
            },
        }
        if not ready:
            return JSONResponse(status_code=503, content=payload)
        return payload

    return app


app = create_app()


__all__ = ["app", "create_app"]
