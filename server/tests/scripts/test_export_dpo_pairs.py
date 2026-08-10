"""DPO pair export: builds one training pair per evaluation from EDIT feedback."""

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


def _seed_evaluation(db_session, *, user_id, criteria=None):
    """Seed one evaluation with an ITSO AgentResult and the given criteria.

    `criteria` defaults to 3 criteria, each with a distinct original
    score/justification, to exercise merging across multiple criteria per
    evaluation.
    """
    if criteria is None:
        criteria = [
            ("itso-01", 4, "No plagiarism detected."),
            ("itso-02", 3, "Bibliography section found with 5 entries."),
            ("itso-03", 2, "No student data confidentiality statement found."),
        ]

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


def test_export_merges_one_edit_into_full_evaluation_response(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-02",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification=(
            "In-text citations sufficient; no separate bibliography required."
        ),
    )

    pairs = list(export_dpo_pairs(db_session))

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.prompt == '{"agent": "itso", "document_chunks": []}'
    chosen = json.loads(pair.chosen)["criterion_scores"]
    rejected = json.loads(pair.rejected)["criterion_scores"]

    assert chosen["itso-02"] == {
        "score": 4,
        "justification": (
            "In-text citations sufficient; no separate bibliography required."
        ),
    }
    assert rejected["itso-02"] == {
        "score": 3,
        "justification": "Bibliography section found with 5 entries.",
    }
    for cid in ("itso-01", "itso-03"):
        assert chosen[cid] == rejected[cid]
    assert set(chosen) == {"itso-01", "itso-02", "itso-03"}
    assert pair.reviewer_ids == frozenset({admin_user.user_id})


def test_export_skips_evaluation_with_no_real_edit(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="ACCEPT",
        user_id=admin_user.user_id,
        user_role="admin",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-02",
        agent_name="itso",
        action="REJECT",
        user_id=admin_user.user_id,
        user_role="admin",
    )

    assert list(export_dpo_pairs(db_session)) == []


def test_export_skips_evaluation_where_only_edit_is_degenerate(
    db_session, admin_user, caplog
):
    caplog.set_level(logging.WARNING, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="No plagiarism detected.",
    )

    pairs = list(export_dpo_pairs(db_session))
    assert pairs == []
    assert "no criterion had a real correction survive" in caplog.text


def test_export_tracks_multiple_reviewers_on_one_evaluation(
    db_session, admin_user, faculty_user
):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="Minor concern noted, not disqualifying.",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="EDIT",
        user_id=faculty_user.user_id,
        user_role="admin",
        score=4,
        justification="Confidentiality addressed in section 2.",
    )

    pairs = list(export_dpo_pairs(db_session))

    assert len(pairs) == 1
    assert pairs[0].reviewer_ids == frozenset(
        {admin_user.user_id, faculty_user.user_id}
    )


def test_export_skips_evaluation_missing_prompt_snapshot(
    db_session, admin_user, caplog
):
    caplog.set_level(logging.WARNING, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    db_session.query(AgentResult).filter_by(evaluation_id=job.evaluation_id).update(
        {"prompt_text": None}
    )
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=1,
        justification="corrected",
    )

    pairs = list(export_dpo_pairs(db_session))
    assert pairs == []
    assert "no prompt_text snapshot" in caplog.text


def test_export_ignores_edit_for_unmatched_criterion_id(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # A real edit, so the evaluation still produces a pair...
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Reconsidered: partial evidence of concern.",
    )
    # ...and a stray edit referencing a criterion_id that was never
    # scored for this evaluation.
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-99",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="stray",
    )

    pairs = list(export_dpo_pairs(db_session))

    assert len(pairs) == 1
    chosen = json.loads(pairs[0].chosen)["criterion_scores"]
    assert "itso-99" not in chosen
    assert set(chosen) == {"itso-01", "itso-02", "itso-03"}
    assert "itso-99" in caplog.text
    assert "no matching CriterionScore row" in caplog.text


def test_main_reports_diversity_summary(
    db_session, admin_user, tmp_path, monkeypatch, caplog
):
    caplog.set_level(logging.INFO, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="Adjusted for context.",
    )

    output_path = tmp_path / "export.jsonl"
    monkeypatch.setattr(
        "server.core.database.get_session_factory",
        lambda: (lambda: db_session),
    )
    monkeypatch.setattr(sys, "argv", ["export_dpo_pairs.py", str(output_path)])

    from server.scripts import export_dpo_pairs as module

    module.main()

    assert (
        "Wrote 1 DPO pairs across 1 evaluations, 1 documents, 1 reviewers"
        in caplog.text
    )
    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    written = json.loads(lines[0])
    assert set(written) == {"prompt", "chosen", "rejected"}
