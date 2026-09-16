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
        evaluation_id=uuid4(),
        document_id=document_id,
        submitted_by=user_id,
        is_pre_snapshot_legacy=True,
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
    from server.modules.agents.contracts import (
        AdvisoryOutput,
        UngroundedCriterionAdvisory,
    )
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.evaluations.models import EvaluationJob
    from server.modules.synthesis.models import EvaluationFlag
    from server.modules.synthesis.service import (
        get_evaluation_results,
        persist_agent_outputs,
    )
    from server.tests.evaluations.snapshot_test_helpers import (
        make_agent_result,
        prepare_test_snapshots,
    )

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
    chunk_id = uuid4()
    db_session.add(
        DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="evidence text",
            token_count=2,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    db_session.flush()
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=document_id,
        submitted_by=seeded_user.user_id,
        status="EVALUATING",
        partial_without_curriculum=True,
    )
    db_session.add(job)
    db_session.flush()

    prepare_test_snapshots(
        db_session,
        job.evaluation_id,
        partial_without_curriculum=True,
    )
    db_session.commit()

    sme_result = make_agent_result(
        "sme",
        job.evaluation_id,
        document_id,
    )
    gad_result = make_agent_result("gad", job.evaluation_id, document_id)
    itso_result = make_agent_result(
        "itso",
        job.evaluation_id,
        document_id,
        scores_by_criterion={
            "ITSO-01": 3,
            "ITSO-02": 4,
            "ITSO-03": 4,
            "ITSO-04": 4,
            "ITSO-05": 4,
        },
        chunk_ids_by_criterion={
            "ITSO-02": (str(chunk_id),),
            "ITSO-03": (str(chunk_id),),
            "ITSO-04": (str(chunk_id),),
            "ITSO-05": (str(chunk_id),),
        },
        evidence_by_criterion={
            "ITSO-02": ("ev",),
            "ITSO-03": ("ev",),
            "ITSO-04": ("ev",),
            "ITSO-05": ("ev",),
        },
        advisory_outputs=AdvisoryOutput(
            ungrounded_criteria=(
                UngroundedCriterionAdvisory(
                    criterion_id="ITSO-01",
                    reason=(
                        "Model score for ITSO-01 provided without grounded "
                        "evidence — human review required"
                    ),
                ),
            )
        ),
    )

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document_id,
        [sme_result, gad_result, itso_result],
        verify_ownership=lambda db: None,
    )

    flags = (
        db_session.query(EvaluationFlag)
        .filter(
            EvaluationFlag.evaluation_id == job.evaluation_id,
            EvaluationFlag.chunk_id.is_(None),
        )
        .all()
    )
    assert len(flags) == 1
    flag = flags[0]
    assert flag.criterion_id == "ITSO-01"
    assert flag.score == 3
    assert flag.reason == (
        "Model score for ITSO-01 provided without grounded evidence — human "
        "review required"
    )
    assert flag.chunk_id is None
    assert flag.document_id == document_id

    # Test via get_evaluation_results as well
    job.status = "COMPLETED"
    db_session.commit()
    results = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)
    assert len(results.flags) == 1
    assert results.flags[0].criterion_id == "ITSO-01"
    assert results.flags[0].justification == (
        "Model score for ITSO-01 provided without grounded evidence — human "
        "review required"
    )


def test_persist_agent_outputs_stores_group_responses(db_session, seeded_user):
    from server.modules.documents.models import Document
    from server.modules.evaluations.models import EvaluationJob
    from server.modules.synthesis.models import AgentResult
    from server.modules.synthesis.service import persist_agent_outputs
    from server.tests.evaluations.snapshot_test_helpers import (
        make_agent_result,
        prepare_test_snapshots,
    )

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
        partial_without_curriculum=True,
    )
    db_session.add(job)
    db_session.flush()

    prepare_test_snapshots(
        db_session,
        job.evaluation_id,
        partial_without_curriculum=True,
    )
    db_session.commit()

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

    sme_result = make_agent_result(
        "sme",
        job.evaluation_id,
        document_id,
        metadata={
            "group_prompts": {"assessment_alignment": "prompt text"},
            "group_responses": group_responses,
        },
    )
    gad_result = make_agent_result("gad", job.evaluation_id, document_id)
    itso_result = make_agent_result("itso", job.evaluation_id, document_id)

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document_id,
        [sme_result, gad_result, itso_result],
        verify_ownership=lambda db: None,
    )

    saved_row = (
        db_session.query(AgentResult)
        .filter(
            AgentResult.evaluation_id == job.evaluation_id,
            AgentResult.agent_name == "sme",
        )
        .one()
    )
    assert saved_row.group_prompts == {"assessment_alignment": "prompt text"}
    assert saved_row.group_responses == group_responses
    # Ensure raw model text is never stored in group_responses or raw_response
    assert saved_row.raw_response is None


def test_get_evaluation_results_surfaces_item_level_correction(db_session, seeded_user):
    """Full stack: real SME snapshot, real group_responses, an ITEM_REJECT,
    and the API response exposing raw_items + the live-recomputed score."""
    from server.modules.documents.models import Document
    from server.modules.evaluations.models import EvaluationJob
    from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
    from server.modules.synthesis.service import persist_agent_outputs
    from server.tests.evaluations.snapshot_test_helpers import make_agent_result
    from server.tests.rubrics.helpers import seed_all_rubrics

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
        status="COMPLETED",
        target_agent="sme",
    )
    db_session.add(job)
    db_session.flush()

    seed_all_rubrics(db_session)
    resolve_or_reuse_evaluation_snapshots(db_session, job.evaluation_id, ("sme",))
    db_session.commit()

    # OP-01 (ratio_band) real measurement: 2 total_units, both qualifying.
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
        metadata={"group_responses": group_responses},
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document_id,
        [sme_result],
        verify_ownership=lambda db: None,
    )

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

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["sme"].criteria}
    op01 = by_id["OP-01"]

    assert op01.score == 4  # original persisted score is untouched
    assert op01.raw_items is not None
    assert {item.item_id: item.rejected for item in op01.raw_items} == {
        "u1": False,
        "u2": True,
    }
    # 1/2 qualifying units -> 50% coverage -> threshold_3 band.
    assert op01.corrected_score == 3

    # A criterion with no item rejections gets no item-level display at all.
    op02 = by_id["OP-02"]
    assert op02.corrected_score is None


def test_persist_agent_outputs_saves_captured_generations(db_session, seeded_user):
    """Verify CapturedGeneration dataclasses are persisted to agent_generations."""
    import hashlib

    from server.modules.agents.contracts import CapturedGeneration
    from server.modules.documents.models import Document
    from server.modules.evaluations.models import EvaluationJob
    from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
    from server.modules.synthesis.models import AgentGeneration
    from server.modules.synthesis.service import persist_agent_outputs
    from server.tests.evaluations.snapshot_test_helpers import make_agent_result
    from server.tests.rubrics.helpers import seed_all_rubrics

    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="test_doc_gens",
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
        status="COMPLETED",
        target_agent="sme",
    )
    db_session.add(job)
    db_session.flush()

    seed_all_rubrics(db_session)
    resolve_or_reuse_evaluation_snapshots(db_session, job.evaluation_id, ("sme",))
    db_session.commit()

    p_text = "Prompt instructions for SME"
    r_text = '{"criterion_measurements": []}'
    captured_gen = CapturedGeneration(
        unit_key="unit_1",
        criterion_ids=("OP-01", "OP-02"),
        prompt_text=p_text,
        prompt_messages=({"role": "user", "content": p_text},),
        response_text=r_text,
        response_json={"criterion_measurements": []},
        response_contract_key="sme_measurement_v1",
        response_contract_version=1,
        model_name="test-model",
        envelope_status="ok",
        generation_provenance={"time": 1.23},
    )

    sme_result = make_agent_result(
        "sme",
        job.evaluation_id,
        document_id,
        generations=(captured_gen,),
    )

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document_id,
        [sme_result],
        verify_ownership=lambda db: None,
    )

    gens = (
        db_session.query(AgentGeneration)
        .filter(AgentGeneration.evaluation_id == job.evaluation_id)
        .all()
    )
    assert len(gens) == 1
    g = gens[0]
    assert g.unit_key == "unit_1"
    assert g.criterion_ids == ["OP-01", "OP-02"]
    assert g.prompt_text == p_text
    assert g.prompt_sha256 == hashlib.sha256(p_text.encode("utf-8")).hexdigest()
    assert g.response_text == r_text
    assert g.response_sha256 == hashlib.sha256(r_text.encode("utf-8")).hexdigest()
    assert g.capture_origin == "native"
    assert g.envelope_status == "ok"
    assert g.model_name == "test-model"
    assert g.response_contract_key == "sme_measurement_v1"
    assert g.agent_id == "sme"
