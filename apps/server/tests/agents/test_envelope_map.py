"""Tests for reconstructing per-evaluation envelope->criteria mapping."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from server.modules.agents.envelope_map import (
    get_criterion_envelope_key,
    get_envelope_criteria_map,
)
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot


def _make_criterion(code: str, config: object, order: int = 0) -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=f"Title {code}",
        description=f"Description for {code}",
        display_order=order,
        strategy_config=config,
    )


def _sme_snapshot(eval_id: uuid.UUID):
    d1 = (
        _make_criterion(
            "OP-01",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            0,
        ),
    )
    d2 = (
        _make_criterion(
            "A-01",
            CountBandConfig(
                mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
            ),
            0,
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Test SME Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="OP",
                title="Organization",
                display_order=0,
                criteria=d1,
            ),
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="A",
                title="Assessment",
                display_order=1,
                criteria=d2,
            ),
        ),
    )
    return build_evaluation_form_snapshot(eval_id, form)


def test_get_envelope_criteria_map_reconstructs_sme_envelopes():
    eval_id = uuid.uuid4()
    snapshot = _sme_snapshot(eval_id)

    with patch(
        "server.modules.agents.envelope_map.load_verified_agent_snapshot",
        return_value=snapshot,
    ):
        envelope_map = get_envelope_criteria_map(
            db=object(), evaluation_id=eval_id, agent_id="sme"
        )

    assert set(envelope_map.keys()) == {"envelope_0", "envelope_1"}
    assert [c.criterion_code for c in envelope_map["envelope_0"]] == ["OP-01"]
    assert [c.criterion_code for c in envelope_map["envelope_1"]] == ["A-01"]


def test_get_envelope_criteria_map_succeeds_with_multi_agent_evaluation():
    """Verify that get_envelope_criteria_map succeeds when evaluation has snapshots

    for multiple agents (e.g. sme, coordinator, gad, itso).
    """
    eval_id = uuid.uuid4()
    sme_snap = _sme_snapshot(eval_id)

    def fake_load_verified_agent_snapshot(db, evaluation_id, agent_id):
        assert evaluation_id == eval_id
        if agent_id == "sme":
            return sme_snap
        raise AssertionError(f"Unexpected agent requested: {agent_id}")

    with patch(
        "server.modules.agents.envelope_map.load_verified_agent_snapshot",
        side_effect=fake_load_verified_agent_snapshot,
    ):
        envelope_map = get_envelope_criteria_map(
            db=object(), evaluation_id=eval_id, agent_id="sme"
        )

    assert set(envelope_map.keys()) == {"envelope_0", "envelope_1"}
    assert [c.criterion_code for c in envelope_map["envelope_0"]] == ["OP-01"]


def test_get_criterion_envelope_key_finds_containing_envelope():
    eval_id = uuid.uuid4()
    snapshot = _sme_snapshot(eval_id)

    with patch(
        "server.modules.agents.envelope_map.load_verified_agent_snapshot",
        return_value=snapshot,
    ):
        key = get_criterion_envelope_key(
            db=object(), evaluation_id=eval_id, agent_id="sme", criterion_id="A-01"
        )
        missing = get_criterion_envelope_key(
            db=object(), evaluation_id=eval_id, agent_id="sme", criterion_id="NOPE"
        )

    assert key == "envelope_1"
    assert missing is None


def test_unsupported_agent_raises():
    with pytest.raises(ValueError, match="envelope reconstruction"):
        get_envelope_criteria_map(
            db=object(), evaluation_id=uuid.uuid4(), agent_id="itso"
        )
