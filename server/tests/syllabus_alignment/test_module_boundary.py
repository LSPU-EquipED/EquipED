"""Regression coverage for the standalone syllabus-alignment module boundary."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from server.core.config import Settings
from server.core.database import Base
from server.db.metadata import import_model_modules
from sqlalchemy import create_engine, inspect


def test_fresh_metadata_registers_alignment_table_once() -> None:
    import_model_modules()
    registered = [
        name for name in Base.metadata.tables if name == "syllabus_alignment_runs"
    ]
    assert registered == ["syllabus_alignment_runs"]

    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        table = inspect(engine).get_columns("syllabus_alignment_runs")
        columns = {column["name"] for column in table}
        assert {
            "alignment_id",
            "slm_document_id",
            "syllabus_document_id",
            "requested_by",
        } <= columns
        foreign_keys = inspect(engine).get_foreign_keys("syllabus_alignment_runs")
        assert {fk["referred_table"] for fk in foreign_keys} == {"documents", "users"}
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_startup_recovery_calls_new_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import server.main as main

    calls: list[object] = []
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_session_factory", lambda: "factory")
    monkeypatch.setattr(
        "server.modules.syllabus_alignment.service.fail_interrupted_syllabus_alignments",
        lambda factory: calls.append(factory) or 0,
    )

    main._fail_interrupted_syllabus_alignments()

    assert calls == ["factory"]


def test_app_registers_syllabus_alignment_routes() -> None:
    import server.main as main

    app: FastAPI = main.app
    paths = {route.path for route in app.routes}
    assert "/api/v1/syllabus-alignments" in paths
    assert "/api/v1/syllabus-alignments/current" in paths
    assert "/api/v1/syllabus-alignments/slms" in paths


def test_new_module_has_independent_import_boundary() -> None:
    root = Path(__file__).resolve().parents[3]
    package = root / "server" / "modules" / "syllabus_alignment"
    forbidden = {"server.modules.evaluations", "server.modules.agents"}
    for source_path in package.glob("*.py"):
        tree = ast.parse(source_path.read_text(), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                raise AssertionError(
                    f"forbidden import in {source_path}: {node.module}"
                )
            if isinstance(node, ast.Import):
                assert not any(alias.name in forbidden for alias in node.names)

    script = """
import importlib
for name in (
    'server.modules.syllabus_alignment.router',
    'server.modules.syllabus_alignment.service',
    'server.modules.syllabus_alignment.evaluator',
    'server.modules.syllabus_alignment.models',
):
    importlib.import_module(name)
for name in (
    'server.modules.evaluations.alignment_router',
    'server.modules.evaluations.alignment_service',
    'server.modules.evaluations.alignment_schemas',
    'server.modules.agents.syllabus_alignment',
):
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        continue
    raise AssertionError(name)
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=root, check=False)
    assert result.returncode == 0
