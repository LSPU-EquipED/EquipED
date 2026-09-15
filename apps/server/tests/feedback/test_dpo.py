"""Tests for item-level DPO training pair export."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.dpo import export_item_level_dpo_pairs
from server.modules.feedback.models import PreferenceLog
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.service import persist_agent_outputs
from server.tests.evaluations.snapshot_test_helpers import make_agent_result
from server.tests.rubrics.helpers import seed_all_rubrics


def _seed_sme_evaluation_with_op01(db_session, user_id):
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
        evaluation_id=uuid4(),
        document_id=document_id,
        submitted_by=user_id,
        status="COMPLETED",
        target_agent="sme",
    )
    db_session.add(job)
    db_session.flush()

    seed_all_rubrics(db_session)
    resolve_or_reuse_evaluation_snapshots(db_session, job.evaluation_id, ("sme",))
    db_session.commit()

    op01_measurement = {
        "criterion_id": "OP-01",
        "criterion_title": "Topic Coherence",
        "total_units": [
            {"unit_id": "u1", "evidence": "Unit 1 to Unit 2."},
            {"unit_id": "u2", "evidence": "Unit 2 to Unit 3."},
        ],
        "qualifying_unit_ids": ["u1", "u2"],
        "has_measurable_content": True,
    }
    other_op_measurements = [
        {"criterion_id": cid, "criterion_title": cid, "instances": []}
        for cid in ("OP-02", "OP-03", "OP-04", "OP-05")
    ]
    other_a_measurements = [
        {"criterion_id": cid, "criterion_title": cid, "instances": []}
        for cid in ("A-01", "A-02", "A-03", "A-04", "A-05")
    ]
    group_prompts = {
        "envelope_0": "Score OP-01..OP-05 for this document.",
        "envelope_1": "Score A-01..A-05 for this document.",
    }
    group_responses = {
        "envelope_0": {
            "criterion_measurements": [op01_measurement, *other_op_measurements]
        },
        "envelope_1": {"criterion_measurements": other_a_measurements},
    }

    sme_result = make_agent_result(
        "sme",
        job.evaluation_id,
        document_id,
        scores_by_criterion={"OP-01": 4},
        metadata={"group_prompts": group_prompts, "group_responses": group_responses},
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document_id,
        [sme_result],
        verify_ownership=lambda db: None,
    )
    return job, document_id


def test_export_yields_pair_for_envelope_with_real_change(db_session, seeded_user):
    job, document_id = _seed_sme_evaluation_with_op01(db_session, seeded_user.user_id)

    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="sme",
            criterion_id="OP-01",
            item_id="u2",
            action="ITEM_REJECT",
        )
    )
    db_session.commit()

    pairs = list(export_item_level_dpo_pairs(db_session))

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.evaluation_id == job.evaluation_id
    assert pair.document_id == document_id
    assert pair.reviewer_ids == frozenset({seeded_user.user_id})
    assert pair.prompt == "Score OP-01..OP-05 for this document."

    rejected = json.loads(pair.rejected)
    chosen = json.loads(pair.chosen)
    op01_rejected = next(
        m for m in rejected["criterion_measurements"] if m["criterion_id"] == "OP-01"
    )
    op01_chosen = next(
        m for m in chosen["criterion_measurements"] if m["criterion_id"] == "OP-01"
    )
    assert op01_rejected["qualifying_unit_ids"] == ["u1", "u2"]
    assert op01_chosen["qualifying_unit_ids"] == ["u1"]
    # Untouched criteria in the same envelope are carried through unchanged.
    op02_chosen = next(
        m for m in chosen["criterion_measurements"] if m["criterion_id"] == "OP-02"
    )
    assert op02_chosen == {
        "criterion_id": "OP-02",
        "criterion_title": "OP-02",
        "instances": [],
    }


def test_export_yields_nothing_without_item_level_feedback(db_session, seeded_user):
    _seed_sme_evaluation_with_op01(db_session, seeded_user.user_id)
    pairs = list(export_item_level_dpo_pairs(db_session))
    assert pairs == []


def test_export_skips_when_reject_then_accept_nets_no_real_change(
    db_session, seeded_user
):
    job, _ = _seed_sme_evaluation_with_op01(db_session, seeded_user.user_id)

    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="sme",
            criterion_id="OP-01",
            item_id="u2",
            action="ITEM_REJECT",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="sme",
            criterion_id="OP-01",
            item_id="u2",
            action="ITEM_ACCEPT",
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    db_session.commit()

    pairs = list(export_item_level_dpo_pairs(db_session))
    assert pairs == []
