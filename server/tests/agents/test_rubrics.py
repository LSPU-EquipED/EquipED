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
        "OP-01 | Title: Topic Coherence | Description: Topics are coherent from Unit to Chapter."
        in context
    )
    assert (
        "A-05 | Title: Objective Gauging | Description: Objectives are gauged effectively."
        in context
    )
