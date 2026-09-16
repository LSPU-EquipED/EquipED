"""Tests for score-level DPO training pair export (llm_rubric_guidance criteria)."""

from __future__ import annotations

import json
from unittest.mock import patch

from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult
from server.modules.training_data.dpo import export_score_level_dpo_pairs

_A01_MEASUREMENT = {
    "criterion_id": "A-01",
    "criterion_title": "Learner Transformation",
    "score": 4,
    "evidence": "Analyze the different case scenario presented in relation to HCI",
    "reasoning": "Nearly all tasks engage higher-order thinking.",
}
_A02_MEASUREMENT = {
    "criterion_id": "A-02",
    "criterion_title": "Varied Assessment Tools",
    "score": 3,
    "evidence": "Midterm QUIZ 1",
    "reasoning": "Moderate variety of assessment types.",
}


def _sme_result_with_group_data(db_session, evaluation_job):
    result = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=evaluation_job.evaluation_id, agent_name="sme")
        .one()
    )
    result.group_prompts = {"envelope_1": "Score A-01 and A-02..."}
    result.group_responses = {
        "envelope_1": {
            "summary": "Assessment domain",
            "criterion_measurements": [_A01_MEASUREMENT, _A02_MEASUREMENT],
        }
    }
    db_session.commit()
    return result


def test_exports_pair_for_score_edit(db_session, evaluation_job, admin_user):
    _sme_result_with_group_data(db_session, evaluation_job)
    db_session.add(
        PreferenceLog(
            evaluation_id=evaluation_job.evaluation_id,
            user_id=admin_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 2, "justification": "Mostly recall-level tasks."},
        )
    )
    db_session.commit()

    with patch(
        "server.modules.training_data.dpo.get_envelope_criteria_map",
        return_value={
            "envelope_1": [
                type("C", (), {"criterion_code": "A-01"})(),
                type("C", (), {"criterion_code": "A-02"})(),
            ]
        },
    ):
        pairs = list(export_score_level_dpo_pairs(db_session, ("sme",)))

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.evaluation_id == evaluation_job.evaluation_id
    assert pair.reviewer_ids == frozenset({admin_user.user_id})

    rejected = json.loads(pair.rejected)
    chosen = json.loads(pair.chosen)
    a01_rejected = next(
        m for m in rejected["criterion_measurements"] if m["criterion_id"] == "A-01"
    )
    a01_chosen = next(
        m for m in chosen["criterion_measurements"] if m["criterion_id"] == "A-01"
    )
    assert a01_rejected["score"] == 4
    assert a01_chosen["score"] == 2
    assert a01_chosen["reasoning"] == "Mostly recall-level tasks."
    # A-02, untouched, is identical in both.
    a02_chosen = next(
        m for m in chosen["criterion_measurements"] if m["criterion_id"] == "A-02"
    )
    assert a02_chosen == _A02_MEASUREMENT


def test_no_export_without_feedback(db_session, evaluation_job):
    _sme_result_with_group_data(db_session, evaluation_job)
    assert list(export_score_level_dpo_pairs(db_session, ("sme",))) == []


def test_reject_skips_whole_envelope(db_session, evaluation_job, admin_user):
    _sme_result_with_group_data(db_session, evaluation_job)
    db_session.add(
        PreferenceLog(
            evaluation_id=evaluation_job.evaluation_id,
            user_id=admin_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="REJECT",
        )
    )
    db_session.commit()

    with patch(
        "server.modules.training_data.dpo.get_envelope_criteria_map",
        return_value={
            "envelope_1": [
                type("C", (), {"criterion_code": "A-01"})(),
                type("C", (), {"criterion_code": "A-02"})(),
            ]
        },
    ):
        pairs = list(export_score_level_dpo_pairs(db_session, ("sme",)))

    assert pairs == []


def test_skips_non_score_shaped_measurement(db_session, evaluation_job, admin_user):
    """Guards against ever substituting a score into a count_band/ratio_band
    measurement (e.g. a historical pre-migration SME evaluation)."""
    result = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=evaluation_job.evaluation_id, agent_name="sme")
        .one()
    )
    result.group_prompts = {"envelope_1": "Score A-01..."}
    result.group_responses = {
        "envelope_1": {
            "summary": "Assessment domain",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "Learner Transformation",
                    "instances": [{"excerpt": "some excerpt"}],
                }
            ],
        }
    }
    db_session.commit()
    db_session.add(
        PreferenceLog(
            evaluation_id=evaluation_job.evaluation_id,
            user_id=admin_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 2, "justification": "test"},
        )
    )
    db_session.commit()

    with patch(
        "server.modules.training_data.dpo.get_envelope_criteria_map",
        return_value={"envelope_1": [type("C", (), {"criterion_code": "A-01"})()]},
    ):
        pairs = list(export_score_level_dpo_pairs(db_session, ("sme",)))

    assert pairs == []


def test_export_envelope_status_filtering(db_session, evaluation_job, admin_user):
    result = _sme_result_with_group_data(db_session, evaluation_job)
    db_session.add(
        PreferenceLog(
            evaluation_id=evaluation_job.evaluation_id,
            user_id=admin_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 2, "justification": "Mostly recall-level tasks."},
        )
    )
    db_session.commit()

    with patch(
        "server.modules.training_data.dpo.get_envelope_criteria_map",
        return_value={
            "envelope_1": [
                type("C", (), {"criterion_code": "A-01"})(),
                type("C", (), {"criterion_code": "A-02"})(),
            ]
        },
    ):
        # When envelope_status is 'fallback', envelope is NOT exported
        result.envelope_status = {"envelope_1": "fallback"}
        db_session.commit()
        assert list(export_score_level_dpo_pairs(db_session, ("sme",))) == []

        # When envelope_status is 'repaired', envelope is NOT exported
        result.envelope_status = {"envelope_1": "repaired"}
        db_session.commit()
        assert list(export_score_level_dpo_pairs(db_session, ("sme",))) == []

        # When envelope_status is 'ok', envelope IS exported
        result.envelope_status = {"envelope_1": "ok"}
        db_session.commit()
        pairs = list(export_score_level_dpo_pairs(db_session, ("sme",)))
        assert len(pairs) == 1
