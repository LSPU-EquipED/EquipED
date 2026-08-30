"""Tests for relational rubric loading and formatting."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.repository import activate_revision
from server.modules.rubrics.service import (
    _get_active_rubric_set,
    get_active_rubric_context,
    get_active_rubric_criteria,
    get_active_rubric_descriptions,
    get_active_rubric_scoring_rules,
)
from server.scripts.seed_rubrics import seed_coordinator_v2_if_needed, seed_domain

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_JSON = ROOT / "data" / "rubrics" / "rubrics.json"


def _seed_from_json(db_session) -> None:
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    for rubric_set_data in payload["rubric_sets"]:
        agent_id = str(rubric_set_data["agent_id"])
        version_number = int(rubric_set_data["version_number"])
        raw_status = str(rubric_set_data.get("status", "draft"))
        status = "published" if raw_status == "active" else raw_status
        if agent_id == "coordinator" and version_number == 1:
            status = "retired"

        now = datetime.now(UTC)
        published_at = now if status == "published" else None
        retired_at = now if status == "retired" else None

        rubric_set = RubricSet(
            rubric_set_id=uuid.uuid4(),
            agent_id=agent_id,
            name=str(rubric_set_data["name"]),
            version_number=version_number,
            status=status,
            adapter_key=str(rubric_set_data.get("adapter_key", agent_id)),
            adapter_version=int(rubric_set_data.get("adapter_version", 1)),
            published_at=published_at,
            published_by=None,
            created_by=None,
            retired_at=retired_at,
            retired_by=None,
            created_at=now,
        )
        db_session.add(rubric_set)
        db_session.flush()

        for domain_data in rubric_set_data.get("domains", []):
            seed_domain(db_session, rubric_set.rubric_set_id, agent_id, domain_data)
        db_session.flush()

        if status == "published":
            activate_revision(
                db_session,
                agent_id,
                rubric_set.rubric_set_id,
                actor_id=None,
                is_system=True,
            )
    seed_coordinator_v2_if_needed(db_session)
    db_session.commit()


def test_active_rubric_context_returns_all_rows_per_agent(db_session) -> None:
    _seed_from_json(db_session)

    expected = {
        "sme": (15, 1),
        "coordinator": (5, 2),
        "gad": (9, 1),
        "itso": (9, 1),
    }

    for agent_id, (expected_count, expected_ver) in expected.items():
        context = get_active_rubric_context(agent_id, db=db_session)
        assert len(context) == expected_count
        assert context[0].startswith("[")
        assert context[1] == f"Agent: {agent_id}"
        assert context[2] == f"Version: {expected_ver}"


def test_active_rubric_context_includes_exact_sme_rows(db_session) -> None:
    _seed_from_json(db_session)

    context = get_active_rubric_context("sme", db=db_session)

    assert context[:3] == ["[SME Rubric v1]", "Agent: sme", "Version: 1"]
    assert "Domain: Organization & Presentation" in context
    assert (
        "OP-01 | Title: Topic Coherence | Description: Topics are coherent "
        "from Unit to Chapter."
    ) in context
    assert (
        "A-05 | Title: Objective Gauging | Description: Objectives are gauged "
        "effectively."
    ) in context


def test_active_rubric_context_avoids_n_plus_one_queries(db_session) -> None:
    """Loading rubric context with multiple domains should not issue N+1 queries."""
    _seed_from_json(db_session)

    # Track SQL statements issued during the call.
    from sqlalchemy import event

    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    conn = db_session.connection()
    event.listens_for(conn, "before_cursor_execute")(_count_queries)
    try:
        get_active_rubric_context("sme", db=db_session)
    finally:
        event.remove(conn, "before_cursor_execute", _count_queries)

    # Expected: <= 4 queries (activation + rubric_set + domains + all criteria via JOIN)
    assert query_count <= 4, f"expected <= 4 queries, got {query_count}"


def test_active_rubric_scoring_rules_returns_sme_rules_and_skips_blank(
    db_session,
) -> None:
    _seed_from_json(db_session)

    rules = get_active_rubric_scoring_rules("sme", db=db_session)
    assert set(rules) == {
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
    }
    assert "assessment TYPES" in rules["A-02"]

    sme_a01 = (
        db_session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .join(RubricSet, RubricDomain.rubric_set_id == RubricSet.rubric_set_id)
        .filter(RubricSet.agent_id == "sme", RubricCriterion.criterion_code == "A-01")
        .one()
    )
    sme_a01.scoring_rule = None
    db_session.flush()
    rules_after = get_active_rubric_scoring_rules("sme", db=db_session)
    assert "A-01" not in rules_after
    assert "A-02" in rules_after


def test_active_rubric_scoring_rules_empty_when_no_active_set(db_session) -> None:
    assert get_active_rubric_scoring_rules("sme", db=db_session) == {}


def test_active_rubric_scoring_rules_returns_gad_rules(db_session) -> None:
    _seed_from_json(db_session)

    rules = get_active_rubric_scoring_rules("gad", db=db_session)
    assert set(rules) == {"GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"}
    assert "unique instance" in rules["GAD-01"]


def test_absent_activation_fails_closed(db_session) -> None:
    """When activation pointer is absent, fail closed without guessing published."""
    _seed_from_json(db_session)

    # Delete activation for SME
    db_session.query(RubricAgentActivation).filter_by(agent_id="sme").delete()
    db_session.commit()

    assert _get_active_rubric_set(db_session, "sme") is None
    assert get_active_rubric_context("sme", db=db_session) == []
    assert get_active_rubric_criteria("sme", db=db_session) == {}
    assert get_active_rubric_descriptions("sme", db=db_session) == {}
    assert get_active_rubric_scoring_rules("sme", db=db_session) == {}


def test_invalid_activation_draft_or_retired_fails_closed(db_session) -> None:
    """When activation points to draft or retired set, queries fail closed."""
    _seed_from_json(db_session)

    # Create a draft set
    now = datetime.now(UTC)
    draft_set = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="SME Draft v2",
        version_number=2,
        status="draft",
        adapter_key="sme",
        adapter_version=1,
        created_at=now,
    )
    db_session.add(draft_set)
    db_session.flush()

    # Point activation to draft
    act = db_session.query(RubricAgentActivation).filter_by(agent_id="sme").one()
    act.rubric_set_id = draft_set.rubric_set_id
    db_session.commit()

    assert _get_active_rubric_set(db_session, "sme") is None
    assert get_active_rubric_context("sme", db=db_session) == []

    # Point activation to retired set (Coordinator v1)
    retired_coord = (
        db_session.query(RubricSet)
        .filter_by(agent_id="coordinator", version_number=1)
        .one()
    )
    coord_act = (
        db_session.query(RubricAgentActivation).filter_by(agent_id="coordinator").one()
    )
    coord_act.rubric_set_id = retired_coord.rubric_set_id
    db_session.commit()

    assert _get_active_rubric_set(db_session, "coordinator") is None
    assert get_active_rubric_context("coordinator", db=db_session) == []


def test_activation_agent_mismatch_fails_closed(db_session) -> None:
    """When activation points to a RubricSet of a different agent, fail closed."""
    _seed_from_json(db_session)

    gad_set = (
        db_session.query(RubricSet).filter_by(agent_id="gad", status="published").one()
    )
    sme_act = db_session.query(RubricAgentActivation).filter_by(agent_id="sme").one()
    # Malicious or corrupt activation pointing SME to GAD set
    sme_act.rubric_set_id = gad_set.rubric_set_id
    db_session.commit()

    assert _get_active_rubric_set(db_session, "sme") is None
    assert get_active_rubric_context("sme", db=db_session) == []


def test_activation_pointing_to_nonexistent_rubric_set_fails_closed(db_session) -> None:
    """When activation points to non-existent rubric set ID, fail closed."""
    _seed_from_json(db_session)

    sme_act = db_session.query(RubricAgentActivation).filter_by(agent_id="sme").one()
    sme_act.rubric_set_id = uuid.uuid4()
    db_session.commit()

    assert _get_active_rubric_set(db_session, "sme") is None
    assert get_active_rubric_context("sme", db=db_session) == []
