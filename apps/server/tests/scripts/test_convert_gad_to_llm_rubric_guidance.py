"""Tests for the GAD llm_rubric_guidance conversion script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from server.modules.rubrics.contracts import LlmRubricGuidanceConfig
from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.repository import get_form_definition_by_id
from server.scripts.convert_gad_to_llm_rubric_guidance import main as run_conversion
from server.scripts.seed_rubrics import seed_rubric_set

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_JSON = ROOT / "data" / "rubrics" / "rubrics.json"


@pytest.fixture()
def seeded_gad_v1(db_session):
    """Seed GAD's real v1 published/active rubric, mirroring
    test_bootstrap_refusal.py's seeding pattern for other agents."""
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    gad_payload = next(s for s in payload["rubric_sets"] if s["agent_id"] == "gad")
    rubric_set = seed_rubric_set(db_session, gad_payload)
    db_session.commit()
    return rubric_set


def test_conversion_publishes_v2_without_activating(db_session, seeded_gad_v1) -> None:
    del seeded_gad_v1  # ensures a v1 active GAD rubric exists before conversion
    run_conversion(session=db_session)

    v1 = db_session.query(RubricSet).filter_by(agent_id="gad", version_number=1).one()
    v2 = db_session.query(RubricSet).filter_by(agent_id="gad", adapter_version=2).one()
    assert v2.status == "published"
    assert v2.version_number == 2

    # Not activated: this script never flips rubric_agent_activations.
    activation = db_session.query(RubricAgentActivation).filter_by(agent_id="gad").one()
    assert activation.rubric_set_id == v1.rubric_set_id

    criteria = (
        db_session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == v2.rubric_set_id)
        .all()
    )
    assert len(criteria) == 5
    codes = {c.criterion_code for c in criteria}
    assert codes == {"GAD-01", "GAD-02", "GAD-03", "GAD-04", "GAD-05"}

    # RubricCriterion.strategy_config is a raw JSON dict on the ORM row;
    # parse via the same FormDefinition path production code uses to get
    # the typed, validated strategy config for each criterion.
    v2_form = get_form_definition_by_id(db_session, v2.rubric_set_id)
    assert v2_form is not None
    all_crit_defs = [c for d in v2_form.domains for c in d.criteria]
    assert len(all_crit_defs) == 5
    for crit_def in all_crit_defs:
        assert isinstance(crit_def.strategy_config, LlmRubricGuidanceConfig)
        assert crit_def.strategy_config.level_descriptors is not None
        assert len(crit_def.strategy_config.level_descriptors) == 4
