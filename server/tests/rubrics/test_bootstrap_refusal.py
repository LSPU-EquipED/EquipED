"""Tests for seed_rubrics bootstrap behavior and refusal of destructive overwrites."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from server.modules.rubrics.models import (
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.rubrics.repository import (
    create_draft_from_active,
    get_active_form_definition,
)
from server.scripts.seed_rubrics import (
    seed_coordinator_v3_if_needed,
    seed_rubric_set,
)

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_JSON = ROOT / "data" / "rubrics" / "rubrics.json"


def test_fresh_seed_populates_published_and_activations(db_session):
    """Fresh seed populates published sets, retired Coord v1, and activations."""
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    for rubric_set_data in payload["rubric_sets"]:
        seed_rubric_set(db_session, rubric_set_data)
    seed_coordinator_v3_if_needed(db_session)
    db_session.commit()

    # SME v1 published and active
    sme_form = get_active_form_definition(db_session, "sme")
    assert sme_form is not None
    assert sme_form.version_number == 1
    assert sme_form.adapter_key == "sme"
    assert sme_form.adapter_version == 1

    # Coordinator v1 retired, Coordinator v3 published and active
    coord_v1 = (
        db_session.query(RubricSet)
        .filter_by(agent_id="coordinator", version_number=1)
        .one()
    )
    assert coord_v1.status == "retired"

    coord_form = get_active_form_definition(db_session, "coordinator")
    assert coord_form is not None
    assert coord_form.version_number == 3
    assert coord_form.adapter_version == 2
    all_codes = {
        c.criterion_code for d in coord_form.domains for c in d.criteria
    }
    assert all_codes == {
        "OP-01", "OP-02", "OP-03", "OP-04", "OP-05",
        "A-01", "A-02", "A-03", "A-04", "A-05",
    }
    a05 = next(
        c for d in coord_form.domains for c in d.criteria
        if c.criterion_code == "A-05"
    )
    assert a05.strategy_config.strategy == "curriculum_alignment"

    # GAD v1 published and active
    gad_form = get_active_form_definition(db_session, "gad")
    assert gad_form is not None
    assert gad_form.version_number == 1
    assert len(gad_form.domains[0].criteria) == 5

    # ITSO v1 published and active
    itso_form = get_active_form_definition(db_session, "itso")
    assert itso_form is not None
    assert itso_form.version_number == 1
    assert len(itso_form.domains[0].criteria) == 5

    # Check that system seed actors are None
    activations = db_session.query(RubricAgentActivation).all()
    assert len(activations) == 4
    for act in activations:
        assert act.updated_by is None


def test_seed_refuses_destructive_overwrite_of_published_revision(db_session):
    """Attempting to re-seed an existing published revision raises RuntimeError."""
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    sme_payload = next(s for s in payload["rubric_sets"] if s["agent_id"] == "sme")

    # Initial seed
    seed_rubric_set(db_session, sme_payload)
    db_session.commit()

    # Re-seeding must raise refusal error
    with pytest.raises(RuntimeError, match="Refusing to delete/overwrite"):
        seed_rubric_set(db_session, sme_payload)


def test_seed_refuses_destructive_overwrite_of_retired_revision(db_session):
    """Attempting to re-seed an existing retired revision raises RuntimeError."""
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    coord_payload = next(
        s for s in payload["rubric_sets"] if s["agent_id"] == "coordinator"
    )

    # Initial seed (coordinator v1 becomes retired)
    seed_rubric_set(db_session, coord_payload)
    db_session.commit()

    # Re-seeding must raise refusal error
    with pytest.raises(RuntimeError, match="Refusing to delete/overwrite"):
        seed_rubric_set(db_session, coord_payload)


def test_seed_refuses_overwrite_of_existing_draft_and_preserves_children(db_session):
    """Seed refuses to overwrite an existing draft and leaves its children intact."""
    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    sme_payload = next(s for s in payload["rubric_sets"] if s["agent_id"] == "sme")

    # Initial seed creates SME v1 published and active
    seed_rubric_set(db_session, sme_payload)
    db_session.commit()

    # Create a draft from active (v2)
    admin_id = uuid.uuid4()
    draft = create_draft_from_active(db_session, "sme", actor_id=admin_id)
    # Modify draft child criterion to identify it
    draft_crit = (
        db_session.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == draft.rubric_set_id)
        .first()
    )
    draft_crit.title = "Custom Admin Edited Title"
    db_session.commit()

    # Attempt to seed an incoming draft payload for SME v2
    draft_seed_payload = {
        "name": "Incoming SME Draft v2",
        "version_number": 2,
        "agent_id": "sme",
        "status": "draft",
        "adapter_key": "sme",
        "adapter_version": 1,
        "domains": [
            {
                "code": "OP",
                "title": "Organization & Presentation",
                "display_order": 1,
                "criteria": [
                    {
                        "criterion_code": "OP-02",
                        "title": "Incoming Title",
                        "description": "Incoming desc",
                        "scoring_rule": "Rule",
                        "scoring_strategy": "count_band",
                        "strategy_config": {
                            "strategy": "count_band",
                            "mode": "minimum_count",
                            "threshold_4": 4,
                            "threshold_3": 2,
                            "threshold_2": 1,
                        },
                        "display_order": 1,
                    }
                ],
            }
        ],
    }

    with pytest.raises(
        RuntimeError, match="Refusing to delete/overwrite draft rubric set"
    ):
        seed_rubric_set(db_session, draft_seed_payload)

    # Verify existing draft and its edited children are preserved
    preserved_draft = (
        db_session.query(RubricSet).filter_by(agent_id="sme", version_number=2).one()
    )
    assert preserved_draft.rubric_set_id == draft.rubric_set_id
    refreshed_crit = (
        db_session.query(RubricCriterion)
        .filter_by(rubric_criterion_id=draft_crit.rubric_criterion_id)
        .one()
    )
    assert refreshed_crit.title == "Custom Admin Edited Title"


def test_seed_rejects_invalid_draft_payload_before_insert(db_session):
    """Seed rejects invalid payload (manifest/contract error) before insertion."""
    invalid_draft_payload = {
        "name": "Invalid SME Draft",
        "version_number": 1,
        "agent_id": "sme",
        "status": "draft",
        "adapter_key": "sme",
        "adapter_version": 1,
        "domains": [
            {
                "code": "OP",
                "title": "Organization & Presentation",
                "display_order": 1,
                "criteria": [
                    {
                        "criterion_code": "OP-01",
                        "title": "Invalid Strategy Criterion",
                        "description": "Desc",
                        "scoring_strategy": "unsupported_strategy",
                        "strategy_config": {
                            "strategy": "unsupported_strategy",
                        },
                        "display_order": 1,
                    }
                ],
            }
        ],
    }

    with pytest.raises(
        ValueError,
        match="Input tag 'unsupported_strategy' found using 'strategy'",
    ):
        seed_rubric_set(db_session, invalid_draft_payload)

    # Ensure no rows were added to DB
    assert db_session.query(RubricSet).count() == 0
    assert db_session.query(RubricDomain).count() == 0
    assert db_session.query(RubricCriterion).count() == 0


def test_seed_rejects_unknown_keys_and_invalid_statuses(db_session):
    """Seed strictly rejects unknown fields and invalid status values."""
    base_payload = {
        "agent_id": "sme",
        "name": "SME Rubric",
        "version_number": 1,
        "status": "draft",
        "domains": [
            {
                "code": "OP",
                "title": "Org",
                "display_order": 1,
                "criteria": [
                    {
                        "criterion_code": "OP-01",
                        "title": "Title",
                        "description": "Desc",
                        "display_order": 1,
                    }
                ],
            }
        ],
    }

    # 1. Unknown top-level key
    bad_payload = dict(base_payload)
    bad_payload["unexpected_extra"] = 123
    with pytest.raises(ValueError, match="Unknown fields in rubric set payload"):
        seed_rubric_set(db_session, bad_payload)

    # 2. Invalid status
    bad_status = dict(base_payload)
    bad_status["status"] = "pending_approval"
    with pytest.raises(ValueError, match="Invalid status 'pending_approval'"):
        seed_rubric_set(db_session, bad_status)

    # 3. Unknown domain key
    bad_dom_payload = {
        "agent_id": "sme",
        "name": "SME Rubric",
        "version_number": 1,
        "domains": [
            {
                "code": "OP",
                "title": "Org",
                "display_order": 1,
                "domain_extra": True,
                "criteria": [
                    {
                        "criterion_code": "OP-01",
                        "title": "Title",
                        "description": "Desc",
                        "display_order": 1,
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="Unknown fields in domain"):
        seed_rubric_set(db_session, bad_dom_payload)

    # 4. Unknown criterion key
    bad_crit_payload = {
        "agent_id": "sme",
        "name": "SME Rubric",
        "version_number": 1,
        "domains": [
            {
                "code": "OP",
                "title": "Org",
                "display_order": 1,
                "criteria": [
                    {
                        "criterion_code": "OP-01",
                        "title": "Title",
                        "description": "Desc",
                        "display_order": 1,
                        "invalid_crit_extra": "bad",
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="Unknown fields in criterion"):
        seed_rubric_set(db_session, bad_crit_payload)


def test_seed_rejects_malformed_container_types(db_session):
    """Seed rejects non-dict payload or non-list domains/criteria."""
    # 1. Non-dict payload
    with pytest.raises(ValueError, match="Rubric set payload must be a dict"):
        seed_rubric_set(db_session, ["not", "a", "dict"])

    # 2. Non-list domains
    with pytest.raises(ValueError, match="'domains' must be a non-empty list"):
        seed_rubric_set(
            db_session,
            {
                "agent_id": "sme",
                "name": "SME",
                "version_number": 1,
                "domains": "invalid",
            },
        )

    # 3. Non-list criteria
    with pytest.raises(ValueError, match="'criteria' must be a non-empty list"):
        seed_rubric_set(
            db_session,
            {
                "agent_id": "sme",
                "name": "SME",
                "version_number": 1,
                "domains": [
                    {
                        "code": "OP",
                        "title": "Org",
                        "display_order": 1,
                        "criteria": "invalid",
                    }
                ],
            },
        )


def test_seed_legacy_coordinator_v1_bounded_structure(db_session):
    """Legacy Coordinator v1 bounded by contracts rejects blank/oversized."""
    # Blank domain code
    bad_dom_code = {
        "agent_id": "coordinator",
        "name": "Coordinator Rubric v1",
        "version_number": 1,
        "domains": [
            {
                "code": "   ",
                "title": "Org",
                "display_order": 1,
                "criteria": [
                    {
                        "criterion_code": "OP-01",
                        "title": "Title",
                        "description": "Desc",
                        "display_order": 1,
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="'code' must be non-empty string"):
        seed_rubric_set(db_session, bad_dom_code)

    # Blank criterion title
    bad_crit_title = {
        "agent_id": "coordinator",
        "name": "Coordinator Rubric v1",
        "version_number": 1,
        "domains": [
            {
                "code": "OP",
                "title": "Org",
                "display_order": 1,
                "criteria": [
                    {
                        "criterion_code": "OP-01",
                        "title": "   ",
                        "description": "Desc",
                        "display_order": 1,
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="'title' must be non-empty string"):
        seed_rubric_set(db_session, bad_crit_title)

    # Oversized description (> 4000 chars)
    oversized_crit_desc = {
        "agent_id": "coordinator",
        "name": "Coordinator Rubric v1",
        "version_number": 1,
        "domains": [
            {
                "code": "OP",
                "title": "Org",
                "display_order": 1,
                "criteria": [
                    {
                        "criterion_code": "OP-01",
                        "title": "Title",
                        "description": "x" * 4001,
                        "display_order": 1,
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="String should have at most 4000 characters"):
        seed_rubric_set(db_session, oversized_crit_desc)


def test_seed_deployed_low_prompt_budget_rejects_seed(db_session, monkeypatch):
    """Low deployed prompt budget setting rejects rubric seeding & v2 bootstrap."""
    from server.core.config import Settings

    payload = json.loads(RUBRIC_JSON.read_text(encoding="utf-8"))
    sme_payload = next(s for s in payload["rubric_sets"] if s["agent_id"] == "sme")

    low_settings = Settings(
        sme_total_prompt_budget_chars=10,
        agent_total_prompt_budget_chars=10,
    )
    monkeypatch.setattr(
        "server.modules.rubrics.repository.get_settings", lambda: low_settings
    )

    # 1. seed_rubric_set fails
    with pytest.raises(ValueError, match="exceeds prompt budget 10"):
        seed_rubric_set(db_session, sme_payload)

    # 2. seed_coordinator_v3_if_needed fails
    with pytest.raises(ValueError, match="exceeds prompt budget 10"):
        seed_coordinator_v3_if_needed(db_session)


def test_seed_coordinator_v3_existing_validation_and_activation_handling(db_session):
    """Existing coordinator v3 status guard, missing-activation repair, no-op."""
    now = datetime.now(UTC)

    # 1. Existing v3 with invalid status (draft) fails closed
    v3_draft = RubricSet(
        rubric_set_id=uuid.uuid4(),
        agent_id="coordinator",
        name="Coordinator Rubric v3",
        version_number=3,
        status="draft",
        adapter_key="coordinator",
        adapter_version=2,
        created_at=now,
    )
    db_session.add(v3_draft)
    db_session.flush()

    with pytest.raises(ValueError, match="invalid status 'draft'"):
        seed_coordinator_v3_if_needed(db_session)

    # Drop the malformed stub so the create path can build a real v3
    db_session.delete(v3_draft)
    db_session.flush()

    # 2. Fresh create path builds and activates the real v3
    created = seed_coordinator_v3_if_needed(db_session)
    db_session.commit()
    act = (
        db_session.query(RubricAgentActivation)
        .filter_by(agent_id="coordinator")
        .one()
    )
    assert act.rubric_set_id == created.rubric_set_id
    assert act.updated_by is None

    # 3. Missing activation is repaired back to the existing valid v3
    db_session.delete(act)
    db_session.commit()
    seed_coordinator_v3_if_needed(db_session)
    repaired = (
        db_session.query(RubricAgentActivation)
        .filter_by(agent_id="coordinator")
        .one()
    )
    assert repaired.rubric_set_id == created.rubric_set_id
    assert repaired.updated_by is None

    # 4. Already pointing to v3 is a no-op
    res = seed_coordinator_v3_if_needed(db_session)
    assert res.rubric_set_id == created.rubric_set_id
