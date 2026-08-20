"""SME DPO pair export: one pair per (evaluation, group) with a real edit."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from server.modules.agents.sme.groups import GROUP_CODES
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.dpo.sme import export_sme_dpo_pairs
from server.modules.feedback.service import create_criterion_feedback
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.scripts.export_sme_dpo_pairs import export_pairs

_TITLES = {
    "A-01": "Learner Transformation",
    "A-02": "Varied Assessment Tools",
    "A-03": "Progress Monitoring",
    "A-04": "Prescriptive Feedback",
    "A-05": "Objective Gauging",
    "OP-01": "Topic Coherence",
    "OP-02": "Interactivity",
    "OP-03": "Clear Directions",
    "OP-04": "Accurate Sections",
    "OP-05": "Enhancement Activities",
}


def _seed_sme_evaluation(
    db_session, *, user_id, group_prompts=None, group_responses=None
):
    """Seed one evaluation with an SME AgentResult scoring all 10 criteria."""
    if group_prompts is None:
        group_prompts = {
            "assessment_alignment": "assessment_alignment prompt text",
            "task_execution": "task_execution prompt text",
            "document_wide": "document_wide prompt text",
        }
    if group_responses is None:
        group_responses = {
            group: {
                "summary": "original summary",
                "criterion_scores": [
                    {
                        "criterion_id": code,
                        "criterion_title": _TITLES[code],
                        "score": 3,
                        "justification": "AI original justification",
                        "evidence": ["original evidence"],
                    }
                    for code in codes
                ],
            }
            for group, codes in GROUP_CODES.items()
        }

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
    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name="sme",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="ok",
        success=True,
        group_prompts=group_prompts,
        group_responses=group_responses,
    )
    db_session.add(agent_result)
    db_session.flush()

    for code, title in _TITLES.items():
        db_session.add(
            CriterionScore(
                agent_result_id=agent_result.agent_result_id,
                evaluation_id=job.evaluation_id,
                document_id=document_id,
                criterion_id=code,
                criterion_title=title,
                score=3,
                justification="AI original justification",
            )
        )
    db_session.commit()
    return job


def test_export_yields_one_pair_per_group_with_a_real_correction(
    db_session, admin_user
):
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected justification",
    )

    pairs = list(export_sme_dpo_pairs(db_session))

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.evaluation_id == job.evaluation_id
    assert pair.document_id == job.document_id
    assert pair.prompt == "task_execution prompt text"

    chosen = json.loads(pair.chosen)
    rejected = json.loads(pair.rejected)

    # Summary and structure preserved
    assert chosen["summary"] == "original summary"
    assert rejected["summary"] == "original summary"
    assert len(chosen["criterion_scores"]) == len(GROUP_CODES["task_execution"])
    assert len(rejected["criterion_scores"]) == len(GROUP_CODES["task_execution"])

    chosen_by_id = {c["criterion_id"]: c for c in chosen["criterion_scores"]}
    rejected_by_id = {c["criterion_id"]: c for c in rejected["criterion_scores"]}

    assert set(chosen_by_id) == set(GROUP_CODES["task_execution"])
    assert chosen_by_id["A-01"]["score"] == 4
    assert chosen_by_id["A-01"]["justification"] == "corrected justification"
    assert chosen_by_id["A-01"]["evidence"] == ["original evidence"]

    assert rejected_by_id["A-01"]["score"] == 3
    assert rejected_by_id["A-01"]["justification"] == "AI original justification"
    assert rejected_by_id["A-01"]["evidence"] == ["original evidence"]

    # Non-edited criteria in the same group stay identical
    assert chosen_by_id["OP-02"] == rejected_by_id["OP-02"]

    assert pair.reviewer_ids == frozenset({admin_user.user_id})


def test_export_skips_groups_with_no_group_prompts_snapshot(db_session, admin_user):
    job = _seed_sme_evaluation(
        db_session, user_id=admin_user.user_id, group_prompts={}
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected",
    )

    assert list(export_sme_dpo_pairs(db_session)) == []


def test_export_skips_groups_with_no_group_responses_snapshot(db_session, admin_user):
    job = _seed_sme_evaluation(
        db_session, user_id=admin_user.user_id, group_responses={}
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected",
    )

    assert list(export_sme_dpo_pairs(db_session)) == []


def test_export_skips_groups_with_no_real_change(db_session, admin_user):
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="AI original justification",
    )

    assert list(export_sme_dpo_pairs(db_session)) == []


def test_accept_retracts_earlier_edit(db_session, admin_user):
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    edit_log = create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected",
    )
    edit_log.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    db_session.commit()

    accept_log = create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="ACCEPT",
        user_id=admin_user.user_id,
        user_role="admin",
    )
    accept_log.created_at = datetime(2026, 1, 2, 10, 0, tzinfo=UTC)
    db_session.commit()

    assert list(export_sme_dpo_pairs(db_session)) == []


def test_reject_action_skips_entire_group(db_session, admin_user):
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    # One EDIT on A-01 and one REJECT on OP-02 in same group
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="OP-02",
        agent_name="sme",
        action="REJECT",
        user_id=admin_user.user_id,
        user_role="admin",
    )

    assert list(export_sme_dpo_pairs(db_session)) == []


def test_multiple_groups_yield_independent_pairs(db_session, admin_user):
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected A-01",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-02",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="corrected A-02",
    )

    pairs = list(export_sme_dpo_pairs(db_session))
    assert len(pairs) == 2
    prompts = {p.prompt for p in pairs}
    assert prompts == {
        "task_execution prompt text",
        "assessment_alignment prompt text",
    }


def test_duplicate_agent_results_skipped(db_session, admin_user):
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    # Add second SME AgentResult
    extra_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        agent_name="sme",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model-2",
        summary="ok",
        success=True,
        group_prompts={"task_execution": "prompt"},
        group_responses={"task_execution": {}},
    )
    db_session.add(extra_result)
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected",
    )

    assert list(export_sme_dpo_pairs(db_session)) == []


def test_cli_delegation_wrapper(db_session, admin_user):
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected",
    )

    pairs = list(export_pairs(db_session))
    assert len(pairs) == 1
    assert pairs[0].evaluation_id == job.evaluation_id


def test_wrong_document_agent_result_skipped(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.sme")
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected A-01",
    )

    # Corrupt agent_result document_id to a different document
    wrong_doc_id = uuid4()
    db_session.query(AgentResult).filter_by(
        evaluation_id=job.evaluation_id
    ).update({"document_id": wrong_doc_id})
    db_session.commit()

    pairs = list(export_sme_dpo_pairs(db_session))
    assert pairs == []
    assert "does not match EvaluationJob document_id" in caplog.text


def test_mismatched_score_lineage_skipped(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.sme")
    job = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="corrected A-01",
    )

    # Corrupt one criterion score's document_id
    wrong_doc_id = uuid4()
    db_session.query(CriterionScore).filter_by(
        evaluation_id=job.evaluation_id, criterion_id="A-01"
    ).update({"document_id": wrong_doc_id})
    db_session.commit()

    pairs = list(export_sme_dpo_pairs(db_session))
    assert pairs == []
    assert "has mismatched lineage" in caplog.text


def test_batch_resolution_multiple_evaluations(db_session, admin_user):
    job1 = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)
    job2 = _seed_sme_evaluation(db_session, user_id=admin_user.user_id)

    create_criterion_feedback(
        db_session,
        evaluation_id=job1.evaluation_id,
        criterion_id="A-01",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="Job 1 correction",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job2.evaluation_id,
        criterion_id="OP-04",
        agent_name="sme",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Job 2 correction",
    )

    pairs = list(export_sme_dpo_pairs(db_session))
    assert len(pairs) == 2
    eval_ids = {p.evaluation_id for p in pairs}
    assert eval_ids == {job1.evaluation_id, job2.evaluation_id}

