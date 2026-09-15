"""Tests for 20260829_0002_backfill_gad_scoring_rule migration."""

from __future__ import annotations

import os
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _run(command, config, revision):
    from server.core.config import get_settings

    get_settings.cache_clear()
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ""
    try:
        command(config, revision)
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
        get_settings.cache_clear()


def _seed_minimal_rubrics(conn) -> None:
    conn.execute(
        text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
    )
    conn.execute(text("INSERT INTO alembic_version VALUES ('20260820_0002')"))
    conn.execute(
        text(
            "CREATE TABLE rubric_sets ("
            "rubric_set_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "name TEXT NOT NULL, version_number INTEGER NOT NULL, "
            "status TEXT NOT NULL, created_at DATETIME NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_domains ("
            "rubric_domain_id TEXT PRIMARY KEY, rubric_set_id TEXT NOT NULL, "
            "code TEXT NOT NULL, title TEXT NOT NULL, display_order INTEGER NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_criteria ("
            "rubric_criterion_id TEXT PRIMARY KEY, rubric_domain_id TEXT NOT NULL, "
            "criterion_code TEXT NOT NULL, title TEXT NOT NULL, "
            "description TEXT NOT NULL, display_order INTEGER NOT NULL)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_sets VALUES "
            "('s-sme','sme','SME',1,'active','2026-01-01'),"
            "('s-gad','gad','GAD',1,'active','2026-01-01')"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_domains VALUES "
            "('d-sme','s-sme','A','Assessment',1),"
            "('d-gad','s-gad','GAD','Gender',1)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_criteria VALUES "
            "('c-sme','d-sme','A-02','Varied','desc',2),"
            "('c-gad','d-gad','GAD-01','Stereo','desc',1)"
        )
    )


def test_backfill_sets_gad_rules_and_downgrade_clears_them(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'gad_backfill.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed_minimal_rubrics(conn)

    # Runs 20260829_0001 (add column + backfill sme/coord) then 20260829_0002.
    _run(upgrade, _config(url), "20260829_0002")
    with engine.connect() as conn:
        assert (
            MigrationContext.configure(conn).get_current_revision()
            == "20260829_0002"
        )
        gad_rule = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria "
                 "WHERE rubric_criterion_id='c-gad'")
        ).scalar()
        sme_rule = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria "
                 "WHERE rubric_criterion_id='c-sme'")
        ).scalar()
    assert gad_rule is not None and "unique instance" in gad_rule
    assert sme_rule is not None  # set by 20260829_0001, untouched here

    # Downgrade one step: GAD rows null again, column still present.
    _run(downgrade, _config(url), "20260829_0001")
    with engine.connect() as conn:
        gad_after = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria "
                 "WHERE rubric_criterion_id='c-gad'")
        ).scalar()
        sme_after = conn.execute(
            text("SELECT scoring_rule FROM rubric_criteria "
                 "WHERE rubric_criterion_id='c-sme'")
        ).scalar()
    assert gad_after is None
    assert sme_after is not None  # 0001's backfill still stands

    engine.dispose()
