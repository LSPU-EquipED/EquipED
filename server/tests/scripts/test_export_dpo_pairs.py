"""DPO pair export: builds (prompt, chosen, rejected) triples from EDIT feedback."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.service import create_criterion_feedback
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.scripts.export_dpo_pairs import export_dpo_pairs


def _seed_evaluation(db_session, *, user_id):
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
        agent_name="itso",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="ok",
        success=True,
        prompt_text='{"agent": "itso", "document_chunks": []}',
    )
    db_session.add(agent_result)
    db_session.flush()

    score_row = CriterionScore(
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        criterion_id="itso-03",
        criterion_title="Citation integrity",
        score=3,
        justification="Bibliography section found with 5 entries.",
    )
    db_session.add(score_row)
    db_session.commit()
    return job


def test_export_builds_pair_from_edit_action(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Bibliography entries are not APA-formatted.",
    )

    pairs = list(export_dpo_pairs(db_session))

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair["prompt"] == '{"agent": "itso", "document_chunks": []}'
    assert json.loads(pair["chosen"]) == {
        "score": 2,
        "justification": "Bibliography entries are not APA-formatted.",
    }
    assert json.loads(pair["rejected"]) == {
        "score": 3,
        "justification": "Bibliography section found with 5 entries.",
    }


def test_export_skips_accept_and_reject_actions(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="ACCEPT",
        user_id=admin_user.user_id,
        user_role="admin",
    )

    pairs = list(export_dpo_pairs(db_session))
    assert pairs == []


def test_export_skips_rows_missing_prompt_snapshot(db_session, admin_user, caplog):
    # Pin the capturing handler directly on the exporter's logger so this
    # assertion is immune to ambient global logging state (e.g. another
    # test in the full suite disabling/reconfiguring logging elsewhere).
    caplog.set_level(logging.WARNING, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # Simulate an AgentResult saved before Task 2 shipped (no prompt_text).
    db_session.query(AgentResult).filter_by(evaluation_id=job.evaluation_id).update(
        {"prompt_text": None}
    )
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="corrected",
    )

    pairs = list(export_dpo_pairs(db_session))
    assert pairs == []
    assert "no prompt_text snapshot" in caplog.text
