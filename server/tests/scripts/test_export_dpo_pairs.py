"""DPO pair export: builds one training pair per evaluation from ITSO feedback."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from uuid import uuid4

from server.modules.agents.itso.response import ITSO_CRITERIA, parse_response
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.dpo import export_itso_dpo_pairs
from server.modules.feedback.service import create_criterion_feedback
from server.modules.synthesis.models import AgentResult, CriterionScore


def _seed_evaluation(db_session, *, user_id, criteria=None):
    """Seed one evaluation with an ITSO AgentResult and 5 canonical criteria."""
    if criteria is None:
        criteria = [
            (
                "ITSO-01",
                4,
                "No plagiarism detected.",
                ["chk-1"],
                ["No plagiarism found"],
            ),
            (
                "ITSO-02",
                3,
                "Bibliography section found with 5 entries.",
                ["chk-2"],
                ["Bibliography"],
            ),
            (
                "ITSO-03",
                2,
                "No student data confidentiality statement found.",
                ["chk-3"],
                ["Section 3"],
            ),
            (
                "ITSO-04",
                4,
                "Student confidentiality preserved.",
                ["chk-4"],
                ["Section 4"],
            ),
            (
                "ITSO-05",
                4,
                "Digital rights preserved.",
                ["chk-5"],
                ["Section 5"],
            ),
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
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=document_id,
        submitted_by=user_id,
    )
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name="itso",
        subtotal=3.4,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="ITSO evaluation summary",
        success=True,
        prompt_text='{"agent": "itso", "document_chunks": []}',
    )
    db_session.add(agent_result)
    db_session.flush()

    for item in criteria:
        if len(item) == 3:
            criterion_id, score, justification = item
            chunk_ids = ["chk-default"]
            evidence = ["evidence-default"]
        else:
            criterion_id, score, justification, chunk_ids, evidence = item
        db_session.add(
            CriterionScore(
                agent_result_id=agent_result.agent_result_id,
                evaluation_id=job.evaluation_id,
                document_id=document_id,
                criterion_id=criterion_id,
                criterion_title=f"Title for {criterion_id}",
                score=score,
                justification=justification,
                chunk_ids=json.dumps(chunk_ids),
                evidence=json.dumps(evidence),
            )
        )
    db_session.commit()
    return job


def test_export_full_parser_round_trip_and_canonical_shape(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-02",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="In-text citations sufficient.",
    )

    pairs = list(export_itso_dpo_pairs(db_session))
    assert len(pairs) == 1
    pair = pairs[0]

    # Validate full round trip through actual strict parser
    known_chunks = ["chk-1", "chk-2", "chk-3", "chk-4", "chk-5"]
    parsed_chosen = parse_response(pair.chosen, known_chunk_ids=known_chunks)
    parsed_rejected = parse_response(
        pair.rejected, known_chunk_ids=known_chunks
    )
    assert parsed_chosen["summary"] == "ITSO evaluation summary"
    assert parsed_rejected["summary"] == "ITSO evaluation summary"

    # Validate ordered canonical shape (5 items in exact order)
    chosen_raw = json.loads(pair.chosen)
    rejected_raw = json.loads(pair.rejected)
    chosen_ids = [c["criterion_id"] for c in chosen_raw["criterion_scores"]]
    rejected_ids = [c["criterion_id"] for c in rejected_raw["criterion_scores"]]
    assert chosen_ids == list(ITSO_CRITERIA)
    assert rejected_ids == list(ITSO_CRITERIA)


def test_edited_fields_only_and_evidence_chunk_preservation(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-02",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="Corrected justification for ITSO-02",
    )

    pair = list(export_itso_dpo_pairs(db_session))[0]
    chosen_list = json.loads(pair.chosen)["criterion_scores"]
    rejected_list = json.loads(pair.rejected)["criterion_scores"]
    chosen_scores = {c["criterion_id"]: c for c in chosen_list}
    rejected_scores = {c["criterion_id"]: c for c in rejected_list}

    # ITSO-02: only score and justification differ
    assert chosen_scores["ITSO-02"]["score"] == 4
    assert (
        chosen_scores["ITSO-02"]["justification"]
        == "Corrected justification for ITSO-02"
    )
    assert rejected_scores["ITSO-02"]["score"] == 3
    assert (
        rejected_scores["ITSO-02"]["justification"]
        == "Bibliography section found with 5 entries."
    )
    assert chosen_scores["ITSO-02"]["chunk_ids"] == ["chk-2"]
    assert rejected_scores["ITSO-02"]["chunk_ids"] == ["chk-2"]
    assert chosen_scores["ITSO-02"]["evidence"] == ["Bibliography"]
    assert rejected_scores["ITSO-02"]["evidence"] == ["Bibliography"]

    # All other criteria: identical across chosen and rejected
    for cid in ("ITSO-01", "ITSO-03", "ITSO-04", "ITSO-05"):
        assert chosen_scores[cid] == rejected_scores[cid]


def test_accept_retracts_older_edit(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # Earlier EDIT on ITSO-01
    edit_log = create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="First edit",
    )
    edit_log.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    db_session.commit()

    # Later ACCEPT on ITSO-01 (retracts the edit)
    accept_log = create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="ACCEPT",
        user_id=admin_user.user_id,
        user_role="admin",
    )
    accept_log.created_at = datetime(2026, 1, 2, 10, 0, tzinfo=UTC)
    db_session.commit()

    # With only retracted edit, unit has no active edit -> 0 pairs
    assert list(export_itso_dpo_pairs(db_session)) == []

    # If another criterion has an active EDIT, pair is yielded with ITSO-01 restored
    edit3_log = create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-03",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="Active edit on ITSO-03",
    )
    edit3_log.created_at = datetime(2026, 1, 3, 10, 0, tzinfo=UTC)
    db_session.commit()

    pairs = list(export_itso_dpo_pairs(db_session))
    assert len(pairs) == 1
    chosen = {
        c["criterion_id"]: c
        for c in json.loads(pairs[0].chosen)["criterion_scores"]
    }
    assert chosen["ITSO-01"]["score"] == 4  # original AI score, not 2
    assert chosen["ITSO-01"]["justification"] == "No plagiarism detected."
    assert chosen["ITSO-03"]["score"] == 4  # active edit


def test_current_reject_skips_unit(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.itso")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # Real EDIT on ITSO-01
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Plagiarism detected.",
    )
    # Active REJECT on ITSO-04
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-04",
        agent_name="itso",
        action="REJECT",
        user_id=admin_user.user_id,
        user_role="admin",
    )

    pairs = list(export_itso_dpo_pairs(db_session))
    assert pairs == []
    assert "ITSO unit contains a REJECT action" in caplog.text


def test_no_op_edit_skips_unit(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.itso")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # Edit with same score and justification as original
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="No plagiarism detected.",
    )

    pairs = list(export_itso_dpo_pairs(db_session))
    assert pairs == []
    assert "no criterion had a real correction survive" in caplog.text


def test_missing_prompt_or_result_or_criterion_skips(
    db_session, admin_user, caplog
):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.itso")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # Null out prompt_text
    db_session.query(AgentResult).filter_by(
        evaluation_id=job.evaluation_id
    ).update({"prompt_text": None})
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=1,
        justification="corrected",
    )

    assert list(export_itso_dpo_pairs(db_session)) == []
    assert "missing prompt_text snapshot" in caplog.text


def test_incomplete_criteria_skips_unit(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.itso")
    # Seed only 4 criteria (missing ITSO-05)
    incomplete_criteria = [
        ("ITSO-01", 4, "No plagiarism detected.", ["chk-1"], ["No plagiarism"]),
        ("ITSO-02", 3, "Bibliography found.", ["chk-2"], ["Bibliography"]),
        ("ITSO-03", 2, "Confidentiality.", ["chk-3"], ["Section 3"]),
        ("ITSO-04", 4, "Student data protected.", ["chk-4"], ["Section 4"]),
    ]
    job = _seed_evaluation(
        db_session, user_id=admin_user.user_id, criteria=incomplete_criteria
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Edit on incomplete criteria evaluation",
    )

    assert list(export_itso_dpo_pairs(db_session)) == []
    assert "missing required ITSO criteria" in caplog.text


def test_multiple_reviewers_tracked_on_dpo_pair(
    db_session, admin_user, faculty_user
):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="Admin correction",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-03",
        agent_name="itso",
        action="EDIT",
        user_id=faculty_user.user_id,
        user_role="admin",
        score=4,
        justification="Faculty correction",
    )

    pairs = list(export_itso_dpo_pairs(db_session))
    assert len(pairs) == 1
    assert pairs[0].reviewer_ids == frozenset(
        {admin_user.user_id, faculty_user.user_id}
    )


def test_main_cli_delegates_and_excludes_reviewer_ids_from_jsonl(
    db_session, admin_user, tmp_path, monkeypatch, caplog
):
    caplog.set_level(logging.INFO, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="Adjusted context",
    )

    output_path = tmp_path / "itso_export.jsonl"
    monkeypatch.setattr(
        "server.core.database.get_session_factory",
        lambda: (lambda: db_session),
    )
    monkeypatch.setattr(sys, "argv", ["export_dpo_pairs.py", str(output_path)])

    from server.scripts import export_dpo_pairs as script_module

    script_module.main()

    assert (
        "Wrote 1 DPO pairs across 1 evaluations, 1 documents, 1 reviewers"
        in caplog.text
    )
    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    # Exact JSONL keys: prompt, chosen, rejected. No reviewer IDs exposed
    assert set(record.keys()) == {"prompt", "chosen", "rejected"}
    assert record["prompt"] == '{"agent": "itso", "document_chunks": []}'


def test_duplicate_itso_agent_results_skipped(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.itso")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="Feedback on ambiguous job",
    )

    # Add a SECOND ITSO AgentResult for the same evaluation
    second_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        agent_name="itso",
        subtotal=2.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="second-model",
        summary="Second summary",
        success=True,
        prompt_text='{"agent": "itso", "document_chunks": ["second"]}',
    )
    db_session.add(second_result)
    db_session.flush()

    for cid in ITSO_CRITERIA:
        db_session.add(
            CriterionScore(
                agent_result_id=second_result.agent_result_id,
                evaluation_id=job.evaluation_id,
                document_id=job.document_id,
                criterion_id=cid,
                criterion_title=f"Second Title {cid}",
                score=1,
                justification="Second run justification",
                chunk_ids=json.dumps(["chk-second"]),
                evidence=json.dumps(["evidence-second"]),
            )
        )
    db_session.commit()

    pairs = list(export_itso_dpo_pairs(db_session))
    assert pairs == []
    assert "duplicate ITSO agent_result rows" in caplog.text


def test_criterion_scores_belonging_to_other_agent_result_not_mixed(
    db_session, admin_user
):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # Add an SME AgentResult on the same evaluation with overlapping/other criteria
    sme_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        agent_name="sme",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="sme-model",
        summary="SME summary",
        success=True,
        prompt_text='{"agent": "sme"}',
    )
    db_session.add(sme_result)
    db_session.flush()

    db_session.add(
        CriterionScore(
            agent_result_id=sme_result.agent_result_id,
            evaluation_id=job.evaluation_id,
            document_id=job.document_id,
            criterion_id="A-01",
            criterion_title="SME alignment",
            score=2,
            justification="SME justification",
            chunk_ids=json.dumps(["chk-sme"]),
            evidence=json.dumps(["evidence-sme"]),
        )
    )
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Valid ITSO edit",
    )

    pairs = list(export_itso_dpo_pairs(db_session))
    assert len(pairs) == 1
    pair = pairs[0]
    chosen = json.loads(pair.chosen)
    rejected = json.loads(pair.rejected)
    # Confirm SME criterion A-01 is never mixed into ITSO envelope
    assert "A-01" not in [c["criterion_id"] for c in chosen["criterion_scores"]]
    assert "A-01" not in [c["criterion_id"] for c in rejected["criterion_scores"]]
    assert [c["criterion_id"] for c in chosen["criterion_scores"]] == list(
        ITSO_CRITERIA
    )


def test_wrong_document_agent_result_skipped(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.itso")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Feedback on mismatched doc result",
    )

    # Corrupt agent_result document_id to a different document
    wrong_doc_id = uuid4()
    db_session.query(AgentResult).filter_by(
        evaluation_id=job.evaluation_id
    ).update({"document_id": wrong_doc_id})
    db_session.commit()

    pairs = list(export_itso_dpo_pairs(db_session))
    assert pairs == []
    assert "does not match EvaluationJob document_id" in caplog.text


def test_mismatched_score_lineage_skipped(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.modules.feedback.dpo.itso")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # Corrupt one score's document_id
    wrong_doc_id = uuid4()
    db_session.query(CriterionScore).filter_by(
        evaluation_id=job.evaluation_id, criterion_id="ITSO-02"
    ).update({"document_id": wrong_doc_id})
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Feedback with mismatched score lineage",
    )

    pairs = list(export_itso_dpo_pairs(db_session))
    assert pairs == []
    assert "has mismatched lineage" in caplog.text


def test_batch_resolution_multiple_evaluations(db_session, admin_user):
    job1 = _seed_evaluation(db_session, user_id=admin_user.user_id)
    job2 = _seed_evaluation(db_session, user_id=admin_user.user_id)

    create_criterion_feedback(
        db_session,
        evaluation_id=job1.evaluation_id,
        criterion_id="ITSO-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Job 1 correction",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job2.evaluation_id,
        criterion_id="ITSO-03",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="Job 2 correction",
    )

    pairs = list(export_itso_dpo_pairs(db_session))
    assert len(pairs) == 2
    eval_ids = {p.evaluation_id for p in pairs}
    assert eval_ids == {job1.evaluation_id, job2.evaluation_id}

