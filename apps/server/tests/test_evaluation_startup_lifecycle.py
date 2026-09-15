import asyncio
import logging
import threading
from types import SimpleNamespace

import pytest
from server import main
from server.core.exceptions import ConfigurationError
from server.modules.documents.ingestion import ocr
from server.modules.evaluations import orchestrator


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("WEB_CONCURRENCY", "2"),
        ("UVICORN_WORKERS", "2"),
        ("GUNICORN_CMD_ARGS", "--workers 2"),
        ("GUNICORN_CMD_ARGS", "--workers=2"),
        ("GUNICORN_CMD_ARGS", "-w 2"),
    ],
)
def test_create_app_rejects_known_multi_worker_configuration(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
) -> None:
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    monkeypatch.delenv("UVICORN_WORKERS", raising=False)
    monkeypatch.delenv("GUNICORN_CMD_ARGS", raising=False)
    monkeypatch.setenv(variable, value)

    with pytest.raises(ConfigurationError, match="one worker"):
        main.create_app()


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("WEB_CONCURRENCY", "1"),
        ("UVICORN_WORKERS", "invalid"),
        ("GUNICORN_CMD_ARGS", "--workers 1"),
        ("GUNICORN_CMD_ARGS", "--workers=invalid"),
        ("GUNICORN_CMD_ARGS", "--log-level info"),
    ],
)
def test_create_app_allows_non_multi_worker_configuration(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
) -> None:
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    monkeypatch.delenv("UVICORN_WORKERS", raising=False)
    monkeypatch.delenv("GUNICORN_CMD_ARGS", raising=False)
    monkeypatch.setenv(variable, value)

    main.create_app()


def _app(monkeypatch: pytest.MonkeyPatch, recovery: bool = True):
    settings = SimpleNamespace(
        app_name="test",
        app_version="test",
        api_prefix="/api",
        cors_origins=(),
        cors_allow_credentials=False,
        database_configured=True,
        environment="test",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "import_model_modules", lambda: None)
    monkeypatch.setattr(main, "_bootstrap_admin_if_needed", lambda: None)
    monkeypatch.setattr(main, "_recover_interrupted_evaluations", lambda: recovery)
    monkeypatch.setattr(main, "_fail_interrupted_syllabus_alignments", lambda: None)
    monkeypatch.setattr(main, "_recover_cleanup_pending_documents", lambda: None)
    monkeypatch.setattr(main, "_recover_no_database_uploads", lambda: None)
    monkeypatch.setattr(ocr, "validate_ocr_installation", lambda *_: None)
    return main.create_app()


def _run_lifespan(app, body=None):
    async def run():
        async with app.router.lifespan_context(app):
            if body:
                body()

    asyncio.run(run())


def test_startup_creates_one_daemon_named_thread_and_tracks_stop_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    stopped = threading.Event()

    def drain(*, stop_event):
        entered.set()
        stop_event.wait()
        stopped.set()

    app = _app(monkeypatch)
    monkeypatch.setattr(orchestrator, "drain_evaluation_queue", drain)
    _run_lifespan(app, entered.wait)

    thread = app.state.evaluation_drain_thread
    assert thread is not None
    assert thread.daemon is True
    assert thread.name == "evaluation-drain"
    assert app.state.evaluation_drain_stop_event.is_set()
    assert stopped.is_set()


def test_blocked_drainer_is_daemon_and_shutdown_logs_generic_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    warnings: list[str] = []

    def drain(*, stop_event):
        entered.set()
        release.wait()

    app = _app(monkeypatch)
    monkeypatch.setattr(orchestrator, "drain_evaluation_queue", drain)
    monkeypatch.setattr(
        main.logger,
        "warning",
        lambda message, *args: warnings.append(message % args if args else message),
    )
    try:
        _run_lifespan(app, entered.wait)
        warning_text = "\n".join(warnings)
        assert "shutdown timed out" in warning_text.lower()
        assert "SECRET" not in warning_text
        assert app.state.evaluation_drain_thread.is_alive()
        assert app.state.evaluation_drain_thread.daemon
    finally:
        release.set()
        app.state.evaluation_drain_thread.join(timeout=1)
        assert not app.state.evaluation_drain_thread.is_alive()


def test_cooperative_drainer_joins_without_timeout_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        orchestrator, "drain_evaluation_queue", lambda *, stop_event: stop_event.wait()
    )
    app = _app(monkeypatch)
    with caplog.at_level(logging.WARNING, logger=main.__name__):
        _run_lifespan(app)
    assert "shutdown timed out" not in caplog.text.lower()
    assert not app.state.evaluation_drain_thread.is_alive()


def test_drainer_failure_logs_category_without_exception_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[str] = []

    def drain(*, stop_event):
        raise RuntimeError("SECRET failure")

    app = _app(monkeypatch)
    monkeypatch.setattr(orchestrator, "drain_evaluation_queue", drain)
    monkeypatch.setattr(
        main.logger,
        "warning",
        lambda message, *args: warnings.append(message % args if args else message),
    )
    _run_lifespan(app)
    warning_text = "\n".join(warnings)
    assert "category=evaluation_queue" in warning_text
    assert "reference=unavailable" in warning_text
    assert "SECRET" not in warning_text
    assert "Traceback" not in warning_text


def test_schema_not_ready_does_not_create_thread_or_stop_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = []
    real_thread = threading.Thread
    monkeypatch.setattr(
        threading, "Thread", lambda *a, **k: created.append(real_thread(*a, **k))
    )
    app = _app(monkeypatch, recovery=False)
    _run_lifespan(app)
    assert created == []
    assert app.state.evaluation_drain_thread is None
    assert app.state.evaluation_drain_stop_event is None


def test_recovery_completes_before_drain_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []
    monkeypatch.setattr(
        orchestrator,
        "drain_evaluation_queue",
        lambda *, stop_event: events.append("drain"),
    )
    app = _app(monkeypatch)
    monkeypatch.setattr(
        main,
        "_recover_interrupted_evaluations",
        lambda: events.append("recovery") or True,
    )
    _run_lifespan(app)
    assert events == ["recovery", "drain"]
