"""Tests for relational rubric loading and formatting."""

from __future__ import annotations

import json
from pathlib import Path

from server.modules.rubrics.models import RubricCriterion, RubricDomain, RubricSet
from server.modules.rubrics.service import get_active_rubric_context

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_JSON = ROOT / "data" / "rubrics" / "rubrics.json"


def _seed_from_json(db_session) -> None:
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    for rubric_set_data in payload["rubric_sets"]:
        rubric_set = RubricSet(
            agent_id=rubric_set_data["agent_id"],
            name=rubric_set_data["name"],
            version_number=rubric_set_data["version_number"],
            status=rubric_set_data["status"],
        )
        db_session.add(rubric_set)
        db_session.flush()

        for domain_data in rubric_set_data["domains"]:
            domain = RubricDomain(
                rubric_set_id=rubric_set.rubric_set_id,
                code=domain_data["code"],
                title=domain_data["title"],
                display_order=domain_data["display_order"],
            )
            db_session.add(domain)
            db_session.flush()

            for criterion_data in domain_data["criteria"]:
                db_session.add(
                    RubricCriterion(
                        rubric_domain_id=domain.rubric_domain_id,
                        criterion_code=criterion_data["criterion_code"],
                        title=criterion_data["title"],
                        description=criterion_data["description"],
                        display_order=criterion_data["display_order"],
                        scoring_rule=criterion_data.get("scoring_rule"),
                    )
                )
    db_session.commit()


def test_active_rubric_context_returns_all_rows_per_agent(db_session) -> None:
    _seed_from_json(db_session)

    expected = {
        "sme": 15,
        "coordinator": 15,
        "gad": 9,
        "itso": 9,
    }

    for agent_id, expected_count in expected.items():
        context = get_active_rubric_context(agent_id, db=db_session)
        assert len(context) == expected_count
        assert context[0].startswith("[")
        assert context[1] == f"Agent: {agent_id}"
        assert context[2] == "Version: 1"


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

    # Expected: 1 (rubric_set) + 1 (domains) + 1 (all criteria via JOIN) = 3
    # Before fix: 1 + 1 + N (one per domain) = 1 + 1 + 3 = 5 for SME (3 domains)
    assert query_count == 3, f"expected 3 queries, got {query_count}"


def test_active_rubric_scoring_rules_returns_sme_rules_and_skips_blank(
    db_session,
) -> None:
    from server.modules.rubrics.models import RubricCriterion, RubricDomain, RubricSet
    from server.modules.rubrics.service import get_active_rubric_scoring_rules

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
    from server.modules.rubrics.service import get_active_rubric_scoring_rules

    assert get_active_rubric_scoring_rules("sme", db=db_session) == {}


def test_active_rubric_scoring_rules_returns_gad_rules(db_session) -> None:
    from server.modules.rubrics.service import get_active_rubric_scoring_rules

    _seed_from_json(db_session)

    rules = get_active_rubric_scoring_rules("gad", db=db_session)
    assert set(rules) == {"GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"}
    assert "unique instance" in rules["GAD-01"]
