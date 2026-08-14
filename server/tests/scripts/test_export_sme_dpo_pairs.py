"""SME DPO pair export: one pair per (evaluation, group) with a real edit."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.agents.sme.groups import GROUP_CODES
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.service import create_criterion_feedback
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.scripts.export_sme_dpo_pairs import export_sme_dpo_pairs

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


def _seed_sme_evaluation(db_session, *, user_id, group_prompts=None):
    """Seed one evaluation with an SME AgentResult scoring all 10 criteria."""
    if group_prompts is None:
        group_prompts = {
            "assessment_alignment": "assessment_alignment prompt text",
            "task_execution": "task_execution prompt text",
            "document_wide": "document_wide prompt text",
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
    assert pair.group == "task_execution"
    assert pair.prompt == "task_execution prompt text"
    chosen = json.loads(pair.chosen)["criterion_scores"]
    rejected = json.loads(pair.rejected)["criterion_scores"]
    assert set(chosen) == set(GROUP_CODES["task_execution"])
    assert chosen["A-01"]["score"] == 4
    assert rejected["A-01"]["score"] == 3
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
