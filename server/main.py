"""FastAPI application entry point for the backend scaffold."""

from __future__ import annotations

import logging
import os
import re
import threading
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
from server.core.exceptions import (
    ConfigurationError,
    CoreError,
    InfrastructureUnavailableError,
)
from server.core.llm import probe_local_model_readiness
from server.db.metadata import import_model_modules
from server.modules.auth.service import bootstrap_admin_if_configured

logger = logging.getLogger(__name__)

_LOG_CAT_ALIGNMENT_RATE_LIMIT_SCOPE = "curriculum_alignment_limiter.process_scope"
_EVALUATION_SHUTDOWN_TIMEOUT_SECONDS = 0.25

MODULE_ROUTER_PATHS = (
    "server.modules.documents.router",
    "server.modules.auth.router",
    "server.modules.synthesis.router",
    "server.modules.evaluations.router",
    "server.modules.alignment.syllabus.router",
    "server.modules.alignment.curriculum.router",
    "server.modules.feedback.router",
    "server.modules.admin.router",
    "server.modules.curriculum.router",
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


def _recover_interrupted_evaluations() -> bool:
    """Requeue stale or tokenless non-terminal evaluation jobs.

    Recovery clears stale execution tokens so the queue drain can process the
    jobs later. It never executes evaluation jobs synchronously. Recovery
    failures are logged but do not crash app startup.
    """

    settings = get_settings()
    if not settings.database_configured:
        return False

    try:
        from server.modules.evaluations.orchestrator import (
            recover_interrupted_evaluation_jobs,
        )

        session_factory = get_session_factory()
        from server.modules.evaluations.service import admission_schema_ready

        session = session_factory()
        try:
            if not admission_schema_ready(session):
                logger.warning(
                    "Evaluation startup recovery skipped: category=admission_schema "
                    "reference=unavailable"
                )
                return False
        finally:
            session.close()
        recovered = recover_interrupted_evaluation_jobs(session_factory)
        if recovered:
            logger.info(
                "Evaluation startup recovery re-queued %d job(s).",
                recovered,
            )
        return True
    except Exception as exc:
        logger.warning(
            "Evaluation startup recovery skipped: category=%s reference=unavailable",
            type(exc).__name__[:64],
        )
        return False


def _fail_interrupted_syllabus_alignments() -> None:
    """Close standalone alignment runs whose BackgroundTask was interrupted."""
    settings = get_settings()
    if not settings.database_configured:
        return
    try:
        from server.modules.alignment.syllabus.service import (
            fail_interrupted_syllabus_alignments,
        )

        failed = fail_interrupted_syllabus_alignments(get_session_factory())
        if failed:
            logger.info(
                "Marked %d interrupted syllabus alignment run(s) failed.", failed
            )
    except Exception:
        logger.exception("Syllabus alignment startup recovery failed.")


def _recover_cleanup_pending_documents() -> None:
    """Retry cleanup for documents left in CLEANUP_PENDING status."""
    settings = get_settings()
    if not settings.database_configured:
        return

    try:
        from server.modules.documents.journaling import (
            recover_cleanup_pending_documents,
        )

        session_factory = get_session_factory()
        recovered = recover_cleanup_pending_documents(session_factory)
        if recovered:
            logger.info(
                "Document cleanup startup recovery successfully cleaned up %d file(s).",
                recovered,
            )
    except Exception:
        logger.exception("Cleanup recovery startup check failed.")


def _recover_no_database_uploads() -> None:
    """Clean stale upload artifacts from no-database development runs."""
    try:
        from server.modules.documents.journaling import (
            recover_no_database_upload_journal,
        )

        recovered = recover_no_database_upload_journal()
        if recovered:
            logger.info(
                "No-DB upload startup recovery cleaned up %d artifact(s).",
                recovered,
            )
    except Exception:
        logger.exception("No-DB upload recovery startup check failed.")


def _warn_if_alignment_limits_are_multi_process() -> None:
    """Warn once when runtime worker count weakens process-local limits."""
    web_concurrency = os.getenv("WEB_CONCURRENCY")
    if web_concurrency is None:
        return
    try:
        workers = int(web_concurrency)
    except ValueError:
        return
    if workers <= 1:
        return

    logger.warning(
        "Alignment rate-limit and cooldown checks are process-local in this backend; "
        "with WEB_CONCURRENCY=%d, caps are enforced per worker and may under-enforce "
        "total concurrency and cooldown behavior.",
        workers,
        extra={"category": _LOG_CAT_ALIGNMENT_RATE_LIMIT_SCOPE},
    )


def create_app() -> FastAPI:
    for key in ("WEB_CONCURRENCY", "UVICORN_WORKERS"):
        value = os.getenv(key)
        if value and value.isdigit() and int(value) > 1:
            raise ConfigurationError("Evaluation service requires one worker.")
    gunicorn_args = os.getenv("GUNICORN_CMD_ARGS", "")
    if re.search(r"(?:^|\s)(?:--workers(?:\s+|=)|-w\s+)([2-9]\d*)\b", gunicorn_args):
        raise ConfigurationError("Evaluation service requires one worker.")

    settings = get_settings()
    import_model_modules()

    _warn_if_alignment_limits_are_multi_process()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _bootstrap_admin_if_needed()
        schema_ready = _recover_interrupted_evaluations()
        # Recovery only requeues; evaluation execution is drained after startup.
        drain_thread: threading.Thread | None = None
        drain_stop = threading.Event()
        try:
            from server.modules.evaluations.orchestrator import drain_evaluation_queue

            if schema_ready:

                def run_drain() -> None:
                    try:
                        drain_evaluation_queue(stop_event=drain_stop)
                    except BaseException:
                        logger.warning(
                            "Evaluation queue failed: "
                            "category=evaluation_queue reference=unavailable"
                        )

                drain_thread = threading.Thread(
                    target=run_drain, name="evaluation-drain", daemon=True
                )
                app.state.evaluation_drain_thread = drain_thread
                app.state.evaluation_drain_stop_event = drain_stop
                drain_thread.start()
        except Exception:
            logger.warning(
                "Evaluation queue startup trigger skipped: category=startup "
                "reference=unavailable"
            )
        _fail_interrupted_syllabus_alignments()
        _recover_cleanup_pending_documents()
        _recover_no_database_uploads()
        try:
            from server.modules.documents.ingestion.ocr import validate_ocr_installation

            validate_ocr_installation(settings)
        except Exception as exc:
            logger.warning(f"OCR validation failed at startup: {exc}")
        yield
        if drain_thread is not None:
            drain_stop.set()
            drain_thread.join(timeout=_EVALUATION_SHUTDOWN_TIMEOUT_SECONDS)
            if drain_thread.is_alive():
                # A daemon may be terminated with the process; durable lease
                # and heartbeat startup recovery handle the unfinished job.
                logger.warning(
                    "Evaluation queue shutdown timed out: "
                    "category=shutdown reference=unavailable"
                )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.evaluation_drain_thread = None
    app.state.evaluation_drain_stop_event = None

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
            "ocr": {
                "configured": True,
                "ready": False,
                "detail": "OCR engine has not been validated",
            },
        }

        if settings.database_configured:
            ok, detail = _probe_runtime_dependency("database", get_engine)
            checks["database"] = {"configured": True, "ready": ok, "detail": detail}
            try:
                from server.modules.evaluations.orchestrator import (
                    is_evaluation_admission_schema_ready,
                )

                schema_ok = is_evaluation_admission_schema_ready(get_session_factory())
            except Exception:
                schema_ok = False
            checks["evaluation_admission"] = {
                "configured": True,
                "ready": schema_ok,
                "detail": "ok" if schema_ok else "admission schema unavailable",
            }

        if settings.chroma_configured:
            ok, detail = _probe_runtime_dependency("chroma", get_chroma_client)
            checks["chroma"] = {"configured": True, "ready": ok, "detail": detail}

        if settings.llm_configured:

            def _readiness() -> None:
                probe_local_model_readiness()

            ok, detail = _probe_runtime_dependency("llm", _readiness)
            checks["llm"] = {"configured": True, "ready": ok, "detail": detail}

        try:
            from server.modules.documents.ingestion.ocr import validate_ocr_installation

            ocr_result = validate_ocr_installation(settings)
            if ocr_result["ready"]:
                ocr_detail = "OCR engine is available and fully configured."
            else:
                ocr_detail = (
                    "OCR engine is unavailable or missing required language packs."
                )
            checks["ocr"] = {
                "configured": True,
                "ready": ocr_result["ready"],
                "detail": ocr_detail,
            }
        except Exception:
            logger.exception("Unexpected OCR validation error at /ready endpoint")
            checks["ocr"] = {
                "configured": True,
                "ready": False,
                "detail": "OCR engine is unavailable or misconfigured.",
            }

        is_ocr_required = settings.environment != "development"
        blocking_checks = {
            k: v for k, v in checks.items() if k != "ocr" or is_ocr_required
        }

        ready = all(check["ready"] for check in blocking_checks.values())
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
