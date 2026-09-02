"""Tests for 20260902_0001_coordinator_rubric_v3 migration.

upgrade  -> coordinator activation points at a 10-criterion v3 (adapter_version 2)
downgrade -> coordinator activation restored to v2, v3 rows removed
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]

REV = "20260902_0001"
DOWN = "20260830_0002"

_EXPECTED_CODES = {
    "OP-01",
    "OP-02",
    "OP-03",
    "OP-04",
    "OP-05",
    "A-01",
    "A-02",
    "A-03",
    "A-04",
    "A-05",
}


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


def _seed_minimal(conn, *, seed_v3: bool = False) -> None:
    conn.execute(
        text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
    )
    conn.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": DOWN})
    conn.execute(
        text(
            "CREATE TABLE rubric_sets ("
            "rubric_set_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "name TEXT NOT NULL, version_number INTEGER NOT NULL, "
            "status TEXT NOT NULL, adapter_key TEXT, adapter_version INTEGER, "
            "published_at DATETIME, created_at DATETIME NOT NULL, "
            "CONSTRAINT uq_rubric_sets_agent_version UNIQUE (agent_id, version_number))"
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
            "description TEXT NOT NULL, scoring_rule TEXT, "
            "scoring_strategy TEXT, strategy_config JSON, "
            "display_order INTEGER NOT NULL)"
        )
    )
    conn.execute(
        text(
            "CREATE TABLE rubric_agent_activations ("
            "agent_id TEXT PRIMARY KEY, rubric_set_id TEXT NOT NULL, "
            "updated_by TEXT, updated_at DATETIME NOT NULL)"
        )
    )
    # retired v1 + published v2 (matches migration-built DB state at 20260830_0002)
    conn.execute(
        text(
            "INSERT INTO rubric_sets VALUES "
            "('coord-v1','coordinator','Coordinator Rubric v1',1,'retired',"
            "'coordinator',1,NULL,'2026-01-01'),"
            "('coord-v2','coordinator','Coordinator Rubric v2',2,'published',"
            "'coordinator',1,'2026-01-01','2026-01-01')"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_domains VALUES "
            "('coord-v2-d','coord-v2','A','Assessment',1)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_criteria VALUES "
            "('coord-v2-c','coord-v2-d','A-05','Curriculum Alignment','desc',"
            "'rule','curriculum_alignment',"
            "'{\"strategy\": \"curriculum_alignment\"}',1)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO rubric_agent_activations VALUES "
            "('coordinator','coord-v2',NULL,'2026-01-01')"
        )
    )
    if seed_v3:
        conn.execute(
            text(
                "INSERT INTO rubric_sets VALUES "
                "('coord-v3-pre','coordinator','Coordinator Rubric v3',3,"
                "'published','coordinator',2,'2026-02-01','2026-02-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO rubric_domains VALUES "
                "('coord-v3-d','coord-v3-pre','A','Assessment',2)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO rubric_criteria VALUES "
                "('coord-v3-c','coord-v3-d','A-05','Curriculum Alignment','desc',"
                "NULL,'curriculum_alignment',"
                "'{\"strategy\": \"curriculum_alignment\"}',5)"
            )
        )
        conn.execute(
            text(
                "UPDATE rubric_agent_activations SET rubric_set_id = 'coord-v3-pre' "
                "WHERE agent_id = 'coordinator'"
            )
        )


def _active_coordinator(conn):
    return conn.execute(
        text(
            "SELECT rs.version_number, rs.adapter_version "
            "FROM rubric_agent_activations a "
            "JOIN rubric_sets rs ON rs.rubric_set_id = a.rubric_set_id "
            "WHERE a.agent_id = 'coordinator'"
        )
    ).one()


def _v3_codes(conn):
    return {
        r[0]
        for r in conn.execute(
            text(
                "SELECT c.criterion_code FROM rubric_criteria c "
                "JOIN rubric_domains d ON d.rubric_domain_id = c.rubric_domain_id "
                "JOIN rubric_sets rs ON rs.rubric_set_id = d.rubric_set_id "
                "WHERE rs.agent_id = 'coordinator' AND rs.version_number = 3"
            )
        )
    }


def test_upgrade_activates_coordinator_v3(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'coord_v3.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed_minimal(conn)

    _run(upgrade, _config(url), REV)

    with engine.connect() as conn:
        row = _active_coordinator(conn)
        assert row.version_number == 3
        assert row.adapter_version == 2
        assert _v3_codes(conn) == _EXPECTED_CODES
        strat = conn.execute(
            text(
                "SELECT c.scoring_strategy FROM rubric_criteria c "
                "JOIN rubric_domains d ON d.rubric_domain_id = c.rubric_domain_id "
                "JOIN rubric_sets rs ON rs.rubric_set_id = d.rubric_set_id "
                "WHERE rs.agent_id = 'coordinator' AND rs.version_number = 3 "
                "AND c.criterion_code = 'A-05'"
            )
        ).scalar_one()
        assert strat == "curriculum_alignment"

        rules = conn.execute(
            text(
                "SELECT c.criterion_code, c.scoring_rule FROM rubric_criteria c "
                "JOIN rubric_domains d ON d.rubric_domain_id = c.rubric_domain_id "
                "JOIN rubric_sets rs ON rs.rubric_set_id = d.rubric_set_id "
                "WHERE rs.agent_id = 'coordinator' AND rs.version_number = 3"
            )
        ).all()
        assert len(rules) == 10
        assert all(rule and rule.strip() for _code, rule in rules)
        a05_rule = next(rule for code, rule in rules if code == "A-05")
        assert "curriculum" in a05_rule.lower()
    engine.dispose()


def test_downgrade_restores_coordinator_v2(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'coord_v3_down.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed_minimal(conn)

    _run(upgrade, _config(url), REV)
    _run(downgrade, _config(url), DOWN)

    with engine.connect() as conn:
        row = _active_coordinator(conn)
        assert row.version_number == 2
        remaining = conn.execute(
            text(
                "SELECT COUNT(*) FROM rubric_sets "
                "WHERE agent_id = 'coordinator' AND version_number = 3"
            )
        ).scalar_one()
        assert remaining == 0
        orphan_crit = conn.execute(
            text(
                "SELECT COUNT(*) FROM rubric_criteria WHERE rubric_domain_id "
                "= 'coord-v3-d'"
            )
        ).scalar_one()
        assert orphan_crit == 0
    engine.dispose()


def test_upgrade_idempotent_when_v3_exists(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'coord_v3_idem.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        _seed_minimal(conn, seed_v3=True)

    _run(upgrade, _config(url), REV)

    with engine.connect() as conn:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM rubric_sets "
                "WHERE agent_id = 'coordinator' AND version_number = 3"
            )
        ).scalar_one()
        assert count == 1
        row = _active_coordinator(conn)
        assert row.version_number == 3
    engine.dispose()
