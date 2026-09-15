"""Service-level unit tests for feedback module."""

from __future__ import annotations

from uuid import uuid4

import pytest
from server.modules.feedback.exceptions import (
    EvaluationNotFoundError,
    InvalidFeedbackTargetError,
)
from server.modules.feedback.service import create_criterion_feedback
from server.modules.synthesis.models import AgentResult, CriterionScore


def _role_str(user) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def test_create_criterion_feedback_valid_itso(
    db_session, evaluation_job, admin_user
):
    log = create_criterion_feedback(
        db_session,
        evaluation_id=evaluation_job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="ACCEPT",
        user_id=admin_user.user_id,
        user_role=_role_str(admin_user),
    )
    assert log.agent_name == "itso"
    assert log.criterion_id == "itso-03"
    assert log.action == "ACCEPT"


def test_create_criterion_feedback_valid_sme(
    db_session, evaluation_job, admin_user
):
    log = create_criterion_feedback(
        db_session,
        evaluation_id=evaluation_job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role=_role_str(admin_user),
        score=3,
        justification="Revised justification",
    )
    assert log.agent_name == "sme"
    assert log.criterion_id == "A-01"
    assert log.action == "EDIT"
    assert log.edited_json == {"score": 3, "justification": "Revised justification"}


def test_create_criterion_feedback_unknown_evaluation(
    db_session, admin_user
):
    with pytest.raises(EvaluationNotFoundError):
        create_criterion_feedback(
            db_session,
            evaluation_id=uuid4(),
            criterion_id="itso-03",
            agent_name="itso",
            action="ACCEPT",
            user_id=admin_user.user_id,
            user_role=_role_str(admin_user),
        )


def test_create_criterion_feedback_non_owning_faculty(
    db_session, evaluation_job, faculty_user
):
    with pytest.raises(EvaluationNotFoundError):
        create_criterion_feedback(
            db_session,
            evaluation_id=evaluation_job.evaluation_id,
            criterion_id="itso-03",
            agent_name="itso",
            action="ACCEPT",
            user_id=faculty_user.user_id,
            user_role="faculty",
        )


def test_create_criterion_feedback_unknown_criterion(
    db_session, evaluation_job, admin_user
):
    with pytest.raises(InvalidFeedbackTargetError):
        create_criterion_feedback(
            db_session,
            evaluation_id=evaluation_job.evaluation_id,
            criterion_id="nonexistent-crit",
            agent_name="itso",
            action="ACCEPT",
            user_id=admin_user.user_id,
            user_role="admin",
        )


def test_create_criterion_feedback_wrong_agent(
    db_session, evaluation_job, admin_user
):
    with pytest.raises(InvalidFeedbackTargetError):
        create_criterion_feedback(
            db_session,
            evaluation_id=evaluation_job.evaluation_id,
            criterion_id="itso-03",
            agent_name="sme",
            action="ACCEPT",
            user_id=admin_user.user_id,
            user_role="admin",
        )


def test_create_criterion_feedback_wrong_document(
    db_session, evaluation_job, admin_user
):
    # AgentResult matches agent_name, but CriterionScore has a different document_id
    mismatched_doc_id = uuid4()
    agent_result = (
        db_session.query(AgentResult)
        .filter(
            AgentResult.evaluation_id == evaluation_job.evaluation_id,
            AgentResult.agent_name == "itso",
        )
        .first()
    )
    score = CriterionScore(
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=evaluation_job.evaluation_id,
        document_id=mismatched_doc_id,
        criterion_id="itso-doc-mismatch",
        criterion_title="Doc Mismatch",
        score=3,
        justification="Mismatched doc",
    )
    db_session.add(score)
    db_session.commit()

    with pytest.raises(InvalidFeedbackTargetError):
        create_criterion_feedback(
            db_session,
            evaluation_id=evaluation_job.evaluation_id,
            criterion_id="itso-doc-mismatch",
            agent_name="itso",
            action="ACCEPT",
            user_id=admin_user.user_id,
            user_role="admin",
        )


def test_create_criterion_feedback_wrong_result(
    db_session, evaluation_job, admin_user
):
    # CriterionScore has agent_result_id pointing to another result
    sme_result = (
        db_session.query(AgentResult)
        .filter(
            AgentResult.evaluation_id == evaluation_job.evaluation_id,
            AgentResult.agent_name == "sme",
        )
        .first()
    )
    score = CriterionScore(
        agent_result_id=sme_result.agent_result_id,
        evaluation_id=evaluation_job.evaluation_id,
        document_id=evaluation_job.document_id,
        criterion_id="itso-wrong-result",
        criterion_title="Wrong Result",
        score=3,
        justification="Wrong result link",
    )
    db_session.add(score)
    db_session.commit()

    with pytest.raises(InvalidFeedbackTargetError):
        create_criterion_feedback(
            db_session,
            evaluation_id=evaluation_job.evaluation_id,
            criterion_id="itso-wrong-result",
            agent_name="itso",
            action="ACCEPT",
            user_id=admin_user.user_id,
            user_role="admin",
        )
