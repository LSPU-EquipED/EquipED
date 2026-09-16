"""Tests for item-level (instance/qualifying-unit) correction support."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from server.modules.feedback.exceptions import InvalidFeedbackTargetError
from server.modules.feedback.items import (
    apply_item_rejections,
    extract_raw_items,
    get_corrected_criterion_score,
    get_criterion_measurement,
    get_effective_item_rejections,
    get_effective_item_rejections_batch,
    validate_item_id,
)
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    RatioBandConfig,
)
from server.modules.synthesis.models import AgentResult

_COUNT_MEASUREMENT = {
    "criterion_id": "OP-02",
    "criterion_title": "Interactive Elements",
    "instances": [
        {"excerpt": "Complete this worksheet."},
        {"excerpt": "Activity 1"},
    ],
}

_RATIO_MEASUREMENT = {
    "criterion_id": "OP-01",
    "criterion_title": "Topic Coherence",
    "total_units": [
        {"unit_id": "u1", "evidence": "Unit 1 to Unit 2."},
        {"unit_id": "u2", "evidence": "Unit 2 to Unit 3."},
    ],
    "qualifying_unit_ids": ["u1", "u2"],
    "has_measurable_content": True,
}


def test_extract_raw_items_count_band():
    items = extract_raw_items(_COUNT_MEASUREMENT)
    assert [i.item_id for i in items] == ["instance_0", "instance_1"]
    assert all(i.included for i in items)


def test_extract_raw_items_ratio_band():
    items = extract_raw_items(_RATIO_MEASUREMENT)
    assert [i.item_id for i in items] == ["u1", "u2"]
    assert all(i.included for i in items)


def test_extract_raw_items_unsupported_shape_raises():
    with pytest.raises(InvalidFeedbackTargetError):
        extract_raw_items({"criterion_id": "ITSO-01", "score": 3})


def test_validate_item_id_accepts_known_and_rejects_unknown():
    validate_item_id(_RATIO_MEASUREMENT, "u1")
    with pytest.raises(InvalidFeedbackTargetError):
        validate_item_id(_RATIO_MEASUREMENT, "u999")


def test_apply_item_rejections_count_band_removes_instance():
    corrected = apply_item_rejections(_COUNT_MEASUREMENT, frozenset({"instance_1"}))
    assert len(corrected["instances"]) == 1
    assert corrected["instances"][0]["excerpt"] == "Complete this worksheet."


def test_apply_item_rejections_ratio_band_removes_from_qualifying_only():
    corrected = apply_item_rejections(_RATIO_MEASUREMENT, frozenset({"u2"}))
    assert corrected["qualifying_unit_ids"] == ["u1"]
    # The unit itself stays listed in total_units -- only qualification changes.
    assert len(corrected["total_units"]) == 2


def test_apply_item_rejections_no_rejections_returns_same_object():
    corrected = apply_item_rejections(_RATIO_MEASUREMENT, frozenset())
    assert corrected is _RATIO_MEASUREMENT


def test_get_effective_item_rejections_latest_wins(
    db_session, evaluation_job, admin_user
):
    eval_id = evaluation_job.evaluation_id
    db_session.add(
        PreferenceLog(
            evaluation_id=eval_id,
            user_id=admin_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            item_id="u1",
            action="ITEM_REJECT",
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    rejected = get_effective_item_rejections(db_session, eval_id, "sme", "A-01")
    assert rejected == frozenset({"u1"})

    # A later ITEM_ACCEPT clears the rejection.
    db_session.add(
        PreferenceLog(
            evaluation_id=eval_id,
            user_id=admin_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            item_id="u1",
            action="ITEM_ACCEPT",
            created_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    rejected_after = get_effective_item_rejections(db_session, eval_id, "sme", "A-01")
    assert rejected_after == frozenset()


def test_get_effective_item_rejections_batch_groups_by_agent_and_criterion(
    db_session, evaluation_job, admin_user
):
    eval_id = evaluation_job.evaluation_id
    db_session.add_all(
        [
            PreferenceLog(
                evaluation_id=eval_id,
                user_id=admin_user.user_id,
                agent_name="sme",
                criterion_id="A-01",
                item_id="u1",
                action="ITEM_REJECT",
            ),
            PreferenceLog(
                evaluation_id=eval_id,
                user_id=admin_user.user_id,
                agent_name="sme",
                criterion_id="A-01",
                item_id="u2",
                action="ITEM_REJECT",
            ),
            PreferenceLog(
                evaluation_id=eval_id,
                user_id=admin_user.user_id,
                agent_name="coordinator",
                criterion_id="OP-01",
                item_id="instance_0",
                action="ITEM_REJECT",
            ),
        ]
    )
    db_session.commit()

    batch = get_effective_item_rejections_batch(
        db_session, eval_id, ("sme", "coordinator")
    )

    assert batch[("sme", "A-01")] == frozenset({"u1", "u2"})
    assert batch[("coordinator", "OP-01")] == frozenset({"instance_0"})
    assert ("sme", "OP-01") not in batch


def test_get_criterion_measurement_success(db_session, evaluation_job):
    sme_result = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=evaluation_job.evaluation_id, agent_name="sme")
        .one()
    )
    sme_result.group_responses = {
        "envelope_0": {"criterion_measurements": [_RATIO_MEASUREMENT]}
    }
    db_session.commit()

    with patch(
        "server.modules.feedback.items.get_criterion_envelope_key",
        return_value="envelope_0",
    ):
        measurement = get_criterion_measurement(
            db_session, evaluation_job.evaluation_id, "sme", "OP-01"
        )
    assert measurement["criterion_id"] == "OP-01"


def test_get_criterion_measurement_no_group_responses_raises(
    db_session, evaluation_job
):
    with pytest.raises(InvalidFeedbackTargetError):
        get_criterion_measurement(
            db_session, evaluation_job.evaluation_id, "sme", "A-01"
        )


def test_get_corrected_criterion_score_recomputes_from_rejection(
    db_session, evaluation_job, admin_user
):
    sme_result = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=evaluation_job.evaluation_id, agent_name="sme")
        .one()
    )
    sme_result.group_responses = {
        "envelope_0": {"criterion_measurements": [_RATIO_MEASUREMENT]}
    }
    db_session.add(
        PreferenceLog(
            evaluation_id=evaluation_job.evaluation_id,
            user_id=admin_user.user_id,
            agent_name="sme",
            criterion_id="OP-01",
            item_id="u2",
            action="ITEM_REJECT",
        )
    )
    db_session.commit()

    criterion = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="OP-01",
        title="Topic Coherence",
        description="desc",
        display_order=0,
        strategy_config=RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        ),
    )

    with patch(
        "server.modules.feedback.items.get_criterion_envelope_key",
        return_value="envelope_0",
    ):
        result = get_corrected_criterion_score(
            db_session,
            evaluation_job.evaluation_id,
            "sme",
            "OP-01",
            criterion,
        )

    assert result is not None
    # 1/2 qualifying units -> 50% coverage -> threshold_3 band.
    assert result.score == 3


def test_get_corrected_criterion_score_returns_none_without_rejections(
    db_session, evaluation_job
):
    criterion = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="OP-01",
        title="Topic Coherence",
        description="desc",
        display_order=0,
        strategy_config=RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        ),
    )
    result = get_corrected_criterion_score(
        db_session, evaluation_job.evaluation_id, "sme", "OP-01", criterion
    )
    assert result is None


def test_get_corrected_criterion_score_returns_none_for_non_item_correctable_strategy(
    db_session, evaluation_job,
):
    from server.modules.rubrics.contracts import LlmRubricGuidanceConfig

    criterion = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="ITSO-01",
        title="No IP Issue",
        description="desc",
        display_order=0,
        strategy_config=LlmRubricGuidanceConfig(guidance="score it"),
    )
    result = get_corrected_criterion_score(
        db_session, evaluation_job.evaluation_id, "itso", "ITSO-01", criterion
    )
    assert result is None
