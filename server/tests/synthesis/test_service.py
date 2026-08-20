"""Tests for get_evaluation_results' reviewer_correction surfacing."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.modules.synthesis.service import get_evaluation_results


def _seed(db_session, *, user_id, agent_name="itso"):
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()
    job = EvaluationJob(
        evaluation_id=uuid4(), document_id=document_id, submitted_by=user_id
    )
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name=agent_name,
        subtotal=2.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="ok",
        success=True,
        prompt_text=f'{{"agent": "{agent_name}"}}',
    )
    db_session.add(agent_result)
    db_session.flush()

    criteria = (
        [
            ("A-01", 4, "No plagiarism detected."),
            ("A-02", 1, "No reference section found."),
            ("A-03", 2, "No ownership statement present."),
        ]
        if agent_name == "sme"
        else [
            ("itso-01", 4, "No plagiarism detected."),
            ("itso-02", 1, "No reference section found."),
            ("itso-03", 2, "No ownership statement present."),
        ]
    )
    for criterion_id, score, justification in criteria:
        db_session.add(
            CriterionScore(
                agent_result_id=agent_result.agent_result_id,
                evaluation_id=job.evaluation_id,
                document_id=document_id,
                criterion_id=criterion_id,
                criterion_title=criterion_id,
                score=score,
                justification=justification,
            )
        )
    db_session.commit()
    return job


def test_untouched_criterion_has_no_reviewer_correction(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    assert by_id["itso-01"].reviewer_correction is None


def test_edited_criterion_surfaces_latest_correction(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={"score": 3, "justification": "Reference section is included"},
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    correction = by_id["itso-02"].reviewer_correction
    assert correction is not None
    assert correction.action == "EDIT"
    assert correction.score == 3
    assert correction.justification == "Reference section is included"


def test_rejected_criterion_has_no_score_or_justification(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-03",
            action="REJECT",
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    correction = by_id["itso-03"].reviewer_correction
    assert correction is not None
    assert correction.action == "REJECT"
    assert correction.score is None
    assert correction.justification is None


def test_only_latest_edit_wins(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={"score": 2, "justification": "first correction"},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={
                "score": 3,
                "justification": "second, more recent correction",
            },
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    correction = by_id["itso-02"].reviewer_correction
    assert correction.score == 3
    assert correction.justification == "second, more recent correction"


def test_accept_action_does_not_surface_as_reviewer_correction(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="ACCEPT",
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    assert by_id["itso-01"].reviewer_correction is None


def test_accept_action_clears_earlier_edit_in_synthesis(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={"score": 3, "justification": "earlier correction"},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="ACCEPT",
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    assert by_id["itso-02"].reviewer_correction is None


def test_timestamp_tie_determinism_in_synthesis(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    same_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    id_lower = uuid4()
    id_higher = uuid4()
    if id_lower > id_higher:
        id_lower, id_higher = id_higher, id_lower

    db_session.add(
        PreferenceLog(
            log_id=id_lower,
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={"score": 1, "justification": "lower ID"},
            created_at=same_time,
        )
    )
    db_session.add(
        PreferenceLog(
            log_id=id_higher,
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={"score": 4, "justification": "higher ID wins"},
            created_at=same_time,
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    correction = by_id["itso-02"].reviewer_correction
    assert correction is not None
    assert correction.score == 4
    assert correction.justification == "higher ID wins"


def test_get_evaluation_results_surfaces_sme_reviewer_correction(
    db_session, seeded_user
):
    job = _seed(db_session, user_id=seeded_user.user_id, agent_name="sme")
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 4, "justification": "corrected"},
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["sme"].criteria}
    correction = by_id["A-01"].reviewer_correction
    assert correction is not None
    assert correction.action == "EDIT"
    assert correction.score == 4
    assert correction.justification == "corrected"


def test_persist_agent_outputs_creates_flags_for_ungrounded_criteria(
    db_session, seeded_user
):
    from server.modules.agents.contracts import AgentEvaluationResult
    from server.modules.agents.contracts import CriterionScore as AgentCriterionScore
    from server.modules.synthesis.models import EvaluationFlag
    from server.modules.synthesis.service import persist_agent_outputs

    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="test_doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=seeded_user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=document_id,
        submitted_by=seeded_user.user_id,
        status="EVALUATING",
    )
    db_session.add(job)
    db_session.flush()

    agent_result = AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        subtotal=3.0,
        criterion_scores=(
            AgentCriterionScore("SME-01", "Alignment", 3, "Partially aligned", ()),
            AgentCriterionScore("SME-02", "Depth", 4, "Deeply covered", ()),
        ),
        summary="Evaluation complete",
        model_name="test-model",
        processing_seconds=1.2,
        token_count=100,
        advisory_outputs={
            "ungrounded_criteria": [
                {"criterion_id": "SME-01", "score": 3},
            ]
        },
    )

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document_id,
        [agent_result],
    )

    flags = (
        db_session.query(EvaluationFlag)
        .filter(EvaluationFlag.evaluation_id == job.evaluation_id)
        .all()
    )
    assert len(flags) == 1
    flag = flags[0]
    assert flag.criterion_id == "SME-01"
    assert flag.score == 3
    assert flag.reason == (
        "Model score for SME-01 provided without grounded evidence — human "
        "review required"
    )
    assert flag.chunk_id is None
    assert flag.document_id == document_id

    # Test via get_evaluation_results as well
    job.status = "COMPLETED"
    db_session.commit()
    results = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)
    assert len(results.flags) == 1
    assert results.flags[0].criterion_id == "SME-01"
    assert results.flags[0].justification == (
        "Model score for SME-01 provided without grounded evidence — human "
        "review required"
    )


def test_persist_agent_outputs_stores_group_responses(db_session, seeded_user):
    from server.modules.agents.contracts import (
        AgentEvaluationResult,
    )
    from server.modules.agents.contracts import (
        CriterionScore as AgentCriterionScore,
    )
    from server.modules.documents.models import Document
    from server.modules.evaluations.models import EvaluationJob
    from server.modules.synthesis.models import AgentResult
    from server.modules.synthesis.service import persist_agent_outputs

    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="test_doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=seeded_user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=document_id,
        submitted_by=seeded_user.user_id,
        status="EVALUATING",
    )
    db_session.add(job)
    db_session.flush()

    group_responses = {
        "assessment_alignment": {
            "summary": "ok",
            "criterion_scores": [
                {
                    "criterion_id": "A-02",
                    "criterion_title": "Varied Assessment",
                    "score": 3,
                    "justification": "justification",
                    "evidence": ["evidence"],
                }
            ],
        }
    }

    agent_result = AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        subtotal=3.0,
        criterion_scores=(
            AgentCriterionScore("A-02", "Varied Assessment", 3, "justification", ()),
        ),
        summary="Evaluation complete",
        model_name="test-model",
        processing_seconds=1.2,
        token_count=100,
        metadata={
            "group_prompts": {"assessment_alignment": "prompt text"},
            "group_responses": group_responses,
        },
    )

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document_id,
        [agent_result],
    )

    saved_row = (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .one()
    )
    assert saved_row.group_prompts == {"assessment_alignment": "prompt text"}
    assert saved_row.group_responses == group_responses
    # Ensure raw model text is never stored in group_responses or raw_response
    assert saved_row.raw_response is None
