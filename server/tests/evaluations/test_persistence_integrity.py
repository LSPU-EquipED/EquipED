"""Tests for strict snapshot-bound Layer-3 result persistence integrity."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from server.modules.agents.contracts import (
    AdvisoryOutput,
    AgentEvaluationResult,
    CriterionScore,
    UngroundedCriterionAdvisory,
)
from server.modules.auth.models import User, UserRole
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.rubrics.models import EvaluationFormSnapshot
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
from server.modules.synthesis.models import (
    AgentResult,
    EvaluationFlag,
)
from server.modules.synthesis.models import (
    CriterionScore as StoredScore,
)
from server.modules.synthesis.service import (
    get_evaluation_results,
    load_verified_persisted_agent_results,
    persist_agent_outputs,
)
from server.tests.evaluations.snapshot_test_helpers import (
    SEEDED_FIXTURE_CRITERION_CODES,
    make_agent_result,
    make_scheduled_agent_results,
    prepare_test_snapshots,
)


def _setup_evaluation(
    db_session,
    *,
    partial_without_curriculum: bool = False,
    with_chunk: bool = True,
) -> tuple[User, Document, EvaluationJob, DocumentChunk | None]:
    owner = User(
        user_id=uuid4(),
        name="Faculty Owner",
        email=f"user-{uuid4().hex[:8]}@example.test",
        role=UserRole.FACULTY,
        password_hash="x",
    )
    db_session.add(owner)
    db_session.flush()

    doc = Document(
        document_id=uuid4(),
        title="SLM Syllabus",
        program="BSCS",
        source_type="slm",
        file_path=f"uploads/{uuid4()}.pdf",
        uploaded_by=owner.user_id,
        uploaded_at=datetime.now(UTC),
        page_count=1,
        has_ocr_pages=False,
        processing_status="PROCESSED",
    )
    db_session.add(doc)
    db_session.flush()

    chunk = None
    if with_chunk:
        chunk = DocumentChunk(
            chunk_id=uuid4(),
            document_id=doc.document_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="Evidence text in syllabus",
            token_count=5,
            is_ocr=False,
            chroma_stored=True,
        )
        db_session.add(chunk)
        db_session.flush()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc.document_id,
        syllabus_id=uuid4(),
        curriculum_id=None if partial_without_curriculum else uuid4(),
        status=EvaluationStatus.EVALUATING.value,
        submitted_by=owner.user_id,
        admission_slot=1,
        execution_token=uuid4(),
        partial_without_curriculum=partial_without_curriculum,
    )
    db_session.add(job)
    db_session.flush()

    prepare_test_snapshots(
        db_session,
        job.evaluation_id,
        partial_without_curriculum=partial_without_curriculum,
    )
    db_session.commit()
    return owner, doc, job, chunk


def test_valid_full_evaluation_persistence_sets_snapshot_fk(db_session) -> None:
    owner, doc, job, chunk = _setup_evaluation(
        db_session, partial_without_curriculum=False
    )

    results = make_scheduled_agent_results(
        job.evaluation_id,
        doc.document_id,
        partial_without_curriculum=False,
        chunk_ids_by_criterion={"A-01": (str(chunk.chunk_id),)} if chunk else None,
    )

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    stored_results = (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .all()
    )
    assert len(stored_results) == 4
    by_agent = {r.agent_name: r for r in stored_results}
    assert set(by_agent.keys()) == {"sme", "coordinator", "gad", "itso"}

    snapshots = {
        s.agent_id: s
        for s in db_session.query(EvaluationFormSnapshot)
        .filter(EvaluationFormSnapshot.evaluation_id == job.evaluation_id)
        .all()
    }

    for agent_id, result_row in by_agent.items():
        assert result_row.form_snapshot_id is not None
        assert result_row.form_snapshot_id == snapshots[agent_id].snapshot_id

    sme_scores = (
        db_session.query(StoredScore)
        .filter(StoredScore.agent_result_id == by_agent["sme"].agent_result_id)
        .all()
    )
    assert len(sme_scores) == 10
    assert {s.criterion_id for s in sme_scores} == set(
        SEEDED_FIXTURE_CRITERION_CODES["sme"]
    )

    coord_scores = (
        db_session.query(StoredScore)
        .filter(StoredScore.agent_result_id == by_agent["coordinator"].agent_result_id)
        .all()
    )
    assert len(coord_scores) == 1
    assert coord_scores[0].criterion_id == "A-05"


def test_valid_partial_evaluation_persistence_sets_snapshot_fk(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session, partial_without_curriculum=True)

    results = make_scheduled_agent_results(
        job.evaluation_id,
        doc.document_id,
        partial_without_curriculum=True,
    )

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    stored_results = (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .all()
    )
    assert len(stored_results) == 3
    by_agent = {r.agent_name: r for r in stored_results}
    assert set(by_agent.keys()) == {"sme", "gad", "itso"}
    assert "coordinator" not in by_agent

    for r in stored_results:
        assert r.form_snapshot_id is not None


def test_failed_agent_persists_non_null_snapshot_fk_and_zero_criteria(
    db_session,
) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session, partial_without_curriculum=False)

    ref = uuid4().hex[:16]
    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id, success=True),
        make_agent_result(
            "coordinator",
            job.evaluation_id,
            doc.document_id,
            success=False,
            error_message=f"CurriculumContextMissing (reference: {ref})",
        ),
        make_agent_result("gad", job.evaluation_id, doc.document_id, success=True),
        make_agent_result("itso", job.evaluation_id, doc.document_id, success=True),
    ]

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    stored_results = (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .all()
    )
    assert len(stored_results) == 4
    by_agent = {r.agent_name: r for r in stored_results}

    coord = by_agent["coordinator"]
    assert not coord.success
    assert coord.error_message == f"CurriculumContextMissing (reference: {ref})"
    assert coord.form_snapshot_id is not None

    coord_scores = (
        db_session.query(StoredScore)
        .filter(StoredScore.agent_result_id == coord.agent_result_id)
        .all()
    )
    assert len(coord_scores) == 0


def test_wrong_evaluation_id_raises_integrity_error(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)

    # Pass non-existent evaluation_id
    with pytest.raises(
        EvaluationResultIntegrityError, match="Evaluation job not found"
    ):
        persist_agent_outputs(
            db_session,
            uuid4(),
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # Pass result with wrong evaluation_id
    bad_results = [
        results[0],
        make_agent_result("coordinator", uuid4(), doc.document_id),
        results[2],
        results[3],
    ]
    with pytest.raises(EvaluationResultIntegrityError, match="evaluation"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            bad_results,
            verify_ownership=lambda db: None,
        )


def test_wrong_document_id_raises_integrity_error(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)

    # Document ID parameter mismatch with job
    with pytest.raises(EvaluationResultIntegrityError, match="document_id mismatch"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            uuid4(),
            results,
            verify_ownership=lambda db: None,
        )

    # Agent result document ID mismatch
    bad_results = [
        results[0],
        make_agent_result("coordinator", job.evaluation_id, uuid4()),
        results[2],
        results[3],
    ]
    with pytest.raises(EvaluationResultIntegrityError, match="document_id mismatch"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            bad_results,
            verify_ownership=lambda db: None,
        )


def test_missing_extra_duplicate_agents_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session, partial_without_curriculum=False)

    # 1. Missing agent (3 instead of 4)
    missing_results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(EvaluationResultIntegrityError, match="count does not match"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            missing_results,
            verify_ownership=lambda db: None,
        )

    # 2. Extra / unknown agent
    extra_results = missing_results + [
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("unknown_agent", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(EvaluationResultIntegrityError, match="count does not match"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            extra_results,
            verify_ownership=lambda db: None,
        )

    # 3. Duplicate agent (4 items, but two sme and no coordinator)
    dup_results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(EvaluationResultIntegrityError, match="Duplicate agent"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            dup_results,
            verify_ownership=lambda db: None,
        )


def test_missing_extra_duplicate_criterion_codes_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session, partial_without_curriculum=False)

    # 1. Missing criterion code (SME has 9 instead of 10)
    sme_scores = (
        CriterionScore("OP-01", "OP-01 Title", 3, "justification"),
        CriterionScore("OP-02", "OP-02 Title", 3, "justification"),
        CriterionScore("OP-03", "OP-03 Title", 3, "justification"),
        CriterionScore("OP-04", "OP-04 Title", 3, "justification"),
        CriterionScore("OP-05", "OP-05 Title", 3, "justification"),
        CriterionScore("A-01", "A-01 Title", 3, "justification"),
        CriterionScore("A-02", "A-02 Title", 3, "justification"),
        CriterionScore("A-03", "A-03 Title", 3, "justification"),
        CriterionScore("A-04", "A-04 Title", 3, "justification"),
        # Missing A-05
    )
    bad_sme = AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        subtotal=3.0,
        criterion_scores=sme_scores,
        summary="ok",
        model_name="test",
        processing_seconds=1.0,
        token_count=10,
        success=True,
    )
    results = [
        bad_sme,
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError, match="Criterion code set mismatch"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # 2. Extra / unknown criterion code
    bad_sme_extra = AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        subtotal=3.0,
        criterion_scores=sme_scores
        + (
            CriterionScore("A-05", "A-05 Title", 3, "justification"),
            CriterionScore("UNKNOWN-99", "Unknown", 3, "justification"),
        ),
        summary="ok",
        model_name="test",
        processing_seconds=1.0,
        token_count=10,
        success=True,
    )
    results[0] = bad_sme_extra
    with pytest.raises(
        EvaluationResultIntegrityError, match="Criterion code set mismatch"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # 3. Duplicate criterion code
    bad_sme_dup = AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        subtotal=3.0,
        criterion_scores=sme_scores
        + (
            CriterionScore("A-05", "A-05 Title", 3, "justification"),
            CriterionScore("A-05", "A-05 Duplicate", 3, "justification"),
        ),
        summary="ok",
        model_name="test",
        processing_seconds=1.0,
        token_count=10,
        success=True,
    )
    results[0] = bad_sme_dup
    with pytest.raises(
        EvaluationResultIntegrityError, match="Duplicate criterion code"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_failed_agent_with_criteria_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session, partial_without_curriculum=False)

    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id, success=True),
        AgentEvaluationResult(
            agent_name="coordinator",
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            subtotal=0.0,
            criterion_scores=(
                CriterionScore("A-05", "Curriculum", 1, "Failed but scored"),
            ),
            summary="",
            model_name="test",
            processing_seconds=1.0,
            token_count=0,
            success=False,
            error_message=f"CoordinatorFailure (reference: {uuid4().hex[:16]})",
        ),
        make_agent_result("gad", job.evaluation_id, doc.document_id, success=True),
        make_agent_result("itso", job.evaluation_id, doc.document_id, success=True),
    ]

    with pytest.raises(
        EvaluationResultIntegrityError, match="must not contain criterion scores"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_duplicate_persistence_prevented_when_agent_results_exist(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)

    # First persistence succeeds
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # Second persistence must fail closed
    with pytest.raises(
        EvaluationResultIntegrityError, match="AgentResult rows already exist"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_tampered_snapshot_hash_fails_load_and_persistence(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)

    # Tamper with snapshot hash in DB
    snapshot = (
        db_session.query(EvaluationFormSnapshot)
        .filter(
            EvaluationFormSnapshot.evaluation_id == job.evaluation_id,
            EvaluationFormSnapshot.agent_id == "sme",
        )
        .one()
    )
    snapshot.snapshot_hash = "a" * 64
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Failed to load verified evaluation snapshots",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_missing_snapshot_set_fails_persistence(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)

    # Delete one snapshot row
    snapshot = (
        db_session.query(EvaluationFormSnapshot)
        .filter(
            EvaluationFormSnapshot.evaluation_id == job.evaluation_id,
            EvaluationFormSnapshot.agent_id == "coordinator",
        )
        .one()
    )
    db_session.delete(snapshot)
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Failed to load verified evaluation snapshots",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_advisory_ungrounded_criteria_validation(db_session) -> None:
    owner, doc, job, chunk = _setup_evaluation(db_session)

    # ITSO with ITSO-01 ungrounded (no chunks/evidence) and ITSO-02..05 grounded
    cid = str(chunk.chunk_id) if chunk else str(uuid4())
    itso_result = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        scores_by_criterion={
            "ITSO-01": 3,
            "ITSO-02": 4,
            "ITSO-03": 4,
            "ITSO-04": 4,
            "ITSO-05": 4,
        },
        chunk_ids_by_criterion={
            "ITSO-02": (cid,),
            "ITSO-03": (cid,),
            "ITSO-04": (cid,),
            "ITSO-05": (cid,),
        },
        evidence_by_criterion={
            "ITSO-02": ("evidence",),
            "ITSO-03": ("evidence",),
            "ITSO-04": ("evidence",),
            "ITSO-05": ("evidence",),
        },
        advisory_outputs=AdvisoryOutput(
            ungrounded_criteria=(
                UngroundedCriterionAdvisory(
                    criterion_id="ITSO-01",
                    reason="Model score for ITSO-01 ungrounded",
                ),
            )
        ),
    )
    sme_result = make_agent_result("sme", job.evaluation_id, doc.document_id)
    coord_result = make_agent_result("coordinator", job.evaluation_id, doc.document_id)
    gad_result = make_agent_result("gad", job.evaluation_id, doc.document_id)

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        [sme_result, coord_result, gad_result, itso_result],
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
    assert flags[0].criterion_id == "ITSO-01"
    assert flags[0].criterion_score_id is not None


def test_non_itso_advisory_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    bad_sme = make_agent_result(
        "sme",
        job.evaluation_id,
        doc.document_id,
    )
    object.__setattr__(
        bad_sme,
        "advisory_outputs",
        AdvisoryOutput(
            ungrounded_criteria=(
                UngroundedCriterionAdvisory(
                    criterion_id="A-01", reason="SME cannot have advisory"
                ),
            )
        ),
    )

    results = [
        bad_sme,
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Non-ITSO agents must not have advisory_outputs",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_itso_advisory_omission_and_extra_rejected(db_session) -> None:
    owner, doc, job, chunk = _setup_evaluation(db_session)
    cid = str(chunk.chunk_id) if chunk else str(uuid4())

    # 1. Omission: ITSO-01 is ungrounded but advisory_outputs is None
    bad_itso_omission = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        chunk_ids_by_criterion={
            "ITSO-02": (cid,),
            "ITSO-03": (cid,),
            "ITSO-04": (cid,),
            "ITSO-05": (cid,),
        },
        evidence_by_criterion={
            "ITSO-02": ("ev",),
            "ITSO-03": ("ev",),
            "ITSO-04": ("ev",),
            "ITSO-05": ("ev",),
        },
    )
    object.__setattr__(bad_itso_omission, "advisory_outputs", None)

    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        bad_itso_omission,
    ]
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="ITSO advisory criteria mismatch against derived ungrounded set",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # 2. Extra: ITSO-01 is grounded but claimed as ungrounded in advisory
    bad_itso_extra = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        chunk_ids_by_criterion={
            "ITSO-01": (cid,),
            "ITSO-02": (cid,),
            "ITSO-03": (cid,),
            "ITSO-04": (cid,),
            "ITSO-05": (cid,),
        },
        evidence_by_criterion={
            "ITSO-01": ("ev",),
            "ITSO-02": ("ev",),
            "ITSO-03": ("ev",),
            "ITSO-04": ("ev",),
            "ITSO-05": ("ev",),
        },
        advisory_outputs=AdvisoryOutput(
            ungrounded_criteria=(
                UngroundedCriterionAdvisory(
                    criterion_id="ITSO-01", reason="extra advisory"
                ),
            )
        ),
    )
    results[3] = bad_itso_extra
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="ITSO advisory criteria mismatch against derived ungrounded set",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_itso_unowned_chunk_changing_parity_rejected_before_writes(
    db_session,
) -> None:
    owner, doc, job, chunk = _setup_evaluation(db_session)
    valid_cid = str(chunk.chunk_id) if chunk else str(uuid4())
    fake_cid = str(uuid4())

    # ITSO claims ITSO-01 is grounded using a fake unowned chunk ID.
    # When chunk ownership verification drops fake_cid, ITSO-01 becomes
    # ungrounded, mismatching advisory.
    bad_itso = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        chunk_ids_by_criterion={
            "ITSO-01": (fake_cid,),
            "ITSO-02": (valid_cid,),
            "ITSO-03": (valid_cid,),
            "ITSO-04": (valid_cid,),
            "ITSO-05": (valid_cid,),
        },
        evidence_by_criterion={
            "ITSO-01": ("ev",),
            "ITSO-02": ("ev",),
            "ITSO-03": ("ev",),
            "ITSO-04": ("ev",),
            "ITSO-05": ("ev",),
        },
    )
    object.__setattr__(bad_itso, "advisory_outputs", None)

    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        bad_itso,
    ]
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="ITSO ungrounded criteria changed after chunk ownership",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    assert (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .count()
        == 0
    )


def test_itso_advisory_flag_deletion_forgery_duplicate_recovery_rejected(
    db_session,
) -> None:
    owner, doc, job, chunk = _setup_evaluation(db_session)
    valid_cid = str(chunk.chunk_id) if chunk else str(uuid4())

    # Create ITSO result with ITSO-01 ungrounded
    itso_result = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        chunk_ids_by_criterion={
            "ITSO-02": (valid_cid,),
            "ITSO-03": (valid_cid,),
            "ITSO-04": (valid_cid,),
            "ITSO-05": (valid_cid,),
        },
        evidence_by_criterion={
            "ITSO-02": ("ev",),
            "ITSO-03": ("ev",),
            "ITSO-04": ("ev",),
            "ITSO-05": ("ev",),
        },
    )
    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        itso_result,
    ]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # 1. Flag deletion: delete the null-chunk flag in DB
    flag = (
        db_session.query(EvaluationFlag)
        .filter(
            EvaluationFlag.evaluation_id == job.evaluation_id,
            EvaluationFlag.chunk_id.is_(None),
        )
        .one()
    )
    db_session.delete(flag)
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError, match="ITSO advisory flag count mismatch"
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )

    # 2. Duplicate flag
    itso_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="itso")
        .one()
    )
    score_row = (
        db_session.query(StoredScore)
        .filter_by(evaluation_id=job.evaluation_id, criterion_id="ITSO-01")
        .one()
    )
    flag_1 = EvaluationFlag(
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        agent_result_id=itso_row.agent_result_id,
        criterion_score_id=score_row.criterion_score_id,
        chunk_id=None,
        criterion_id="ITSO-01",
        score=score_row.score,
        reason="reason 1",
    )
    flag_2 = EvaluationFlag(
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        agent_result_id=itso_row.agent_result_id,
        criterion_score_id=score_row.criterion_score_id,
        chunk_id=None,
        criterion_id="ITSO-01",
        score=score_row.score,
        reason="duplicate reason",
    )
    db_session.add_all([flag_1, flag_2])
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError, match="ITSO advisory flag count mismatch"
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_itso_malformed_evidence_or_chunks_type_rejected(db_session) -> None:
    owner, doc, job, chunk = _setup_evaluation(db_session)
    valid_cid = str(chunk.chunk_id) if chunk else str(uuid4())

    # 1. Evidence is a list instead of a tuple
    bad_score_ev = CriterionScore(
        criterion_id="ITSO-01",
        criterion_title="Title",
        score=3,
        justification="j",
        chunk_ids=(valid_cid,),
        evidence=["not", "a", "tuple"],  # type: ignore
    )
    bad_itso_ev = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
    )
    object.__setattr__(
        bad_itso_ev,
        "criterion_scores",
        (bad_score_ev,)
        + tuple(
            CriterionScore(
                criterion_id=c,
                criterion_title=f"{c} Title",
                score=3,
                justification="j",
                chunk_ids=(valid_cid,),
                evidence=("ev",),
            )
            for c in SEEDED_FIXTURE_CRITERION_CODES["itso"]
            if c != "ITSO-01"
        ),
    )
    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        bad_itso_ev,
    ]
    with pytest.raises(
        EvaluationResultIntegrityError, match="evidence must be a tuple"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    object.__setattr__(bad_score_ev, "evidence", ("",))
    with pytest.raises(EvaluationResultIntegrityError, match="Invalid evidence item"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    object.__setattr__(bad_score_ev, "evidence", ("ev",))
    object.__setattr__(bad_score_ev, "chunk_ids", (" ",))
    with pytest.raises(EvaluationResultIntegrityError, match="Invalid chunk_id"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # 2. Chunk_ids is a list instead of a tuple
    bad_score_chunk = CriterionScore(
        criterion_id="ITSO-01",
        criterion_title="Title",
        score=3,
        justification="j",
        chunk_ids=[valid_cid],  # type: ignore
        evidence=("ev",),
    )
    bad_itso_chunk = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
    )
    object.__setattr__(
        bad_itso_chunk,
        "criterion_scores",
        (bad_score_chunk,)
        + tuple(
            CriterionScore(
                criterion_id=c,
                criterion_title=f"{c} Title",
                score=3,
                justification="j",
                chunk_ids=(valid_cid,),
                evidence=("ev",),
            )
            for c in SEEDED_FIXTURE_CRITERION_CODES["itso"]
            if c != "ITSO-01"
        ),
    )
    results[3] = bad_itso_chunk
    with pytest.raises(
        EvaluationResultIntegrityError, match="chunk_ids must be a tuple"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_persisted_chunk_from_foreign_document_rejected_on_recovery(
    db_session,
) -> None:
    owner, doc, job, chunk = _setup_evaluation(db_session)
    valid_cid = str(chunk.chunk_id) if chunk else str(uuid4())

    # Create a foreign document and chunk
    foreign_doc = Document(
        document_id=uuid4(),
        title="Foreign Doc",
        program="BSCS",
        source_type="slm",
        file_path="uploads/foreign.pdf",
        uploaded_by=owner.user_id,
        uploaded_at=datetime.now(UTC),
        processing_status="PROCESSED",
    )
    db_session.add(foreign_doc)
    foreign_chunk = DocumentChunk(
        chunk_id=uuid4(),
        document_id=foreign_doc.document_id,
        source_type="slm",
        agent_domain="all",
        page_number=1,
        text="foreign text",
        token_count=2,
    )
    db_session.add(foreign_chunk)
    db_session.flush()

    itso_result = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        chunk_ids_by_criterion={
            "ITSO-01": (valid_cid,),
            "ITSO-02": (valid_cid,),
            "ITSO-03": (valid_cid,),
            "ITSO-04": (valid_cid,),
            "ITSO-05": (valid_cid,),
        },
        evidence_by_criterion={
            "ITSO-01": ("ev",),
            "ITSO-02": ("ev",),
            "ITSO-03": ("ev",),
            "ITSO-04": ("ev",),
            "ITSO-05": ("ev",),
        },
    )
    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        itso_result,
    ]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # Mutate stored chunk_ids for ITSO-01 to foreign_chunk.chunk_id
    itso_score = (
        db_session.query(StoredScore)
        .filter_by(evaluation_id=job.evaluation_id, criterion_id="ITSO-01")
        .one()
    )
    itso_score.chunk_ids = json.dumps([str(foreign_chunk.chunk_id)])
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Persisted chunk ID does not belong to evaluated document",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_flag_mismatched_result_score_foreign_chunk_rejected_on_recovery(
    db_session,
) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    results = make_scheduled_agent_results(
        job.evaluation_id, doc.document_id, partial_without_curriculum=False
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    sme_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="sme")
        .one()
    )
    itso_score = (
        db_session.query(StoredScore)
        .filter_by(evaluation_id=job.evaluation_id, criterion_id="ITSO-01")
        .one()
    )

    # Add flag connecting SME result to ITSO score
    bad_flag = EvaluationFlag(
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        agent_result_id=sme_row.agent_result_id,  # Mismatched result
        criterion_score_id=itso_score.criterion_score_id,
        chunk_id=uuid4(),  # Foreign chunk
        criterion_id="ITSO-01",
        score=3,
        reason="bad relationship",
    )
    db_session.add(bad_flag)
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError,
        match="EvaluationFlag score and result relationship mismatch",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_flag_from_foreign_evaluation_referencing_current_score_found_and_rejected(
    db_session,
) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    results = make_scheduled_agent_results(
        job.evaluation_id, doc.document_id, partial_without_curriculum=False
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    itso_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="itso")
        .one()
    )
    itso_score = (
        db_session.query(StoredScore)
        .filter_by(evaluation_id=job.evaluation_id, criterion_id="ITSO-01")
        .one()
    )

    # Flag has a foreign evaluation_id, but references current result and score
    foreign_eval_id = uuid4()
    foreign_flag = EvaluationFlag(
        evaluation_id=foreign_eval_id,
        document_id=doc.document_id,
        agent_result_id=itso_row.agent_result_id,
        criterion_score_id=itso_score.criterion_score_id,
        chunk_id=None,
        criterion_id="ITSO-01",
        score=3,
        reason="foreign flag referencing current score",
    )
    db_session.add(foreign_flag)
    db_session.commit()

    # Recovery query uses OR and surfaces this foreign flag
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="EvaluationFlag cross-evaluation or cross-document reference",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_foreign_evaluation_score_referencing_current_result_rejected(
    db_session,
) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    results = make_scheduled_agent_results(
        job.evaluation_id, doc.document_id, partial_without_curriculum=False
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    itso_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="itso")
        .one()
    )

    # Score has foreign evaluation_id but points to current agent_result_id
    foreign_score = StoredScore(
        criterion_score_id=uuid4(),
        agent_result_id=itso_row.agent_result_id,
        evaluation_id=uuid4(),
        document_id=doc.document_id,
        criterion_id="ITSO-01",
        criterion_title="Title",
        score=3,
        justification="j",
    )
    db_session.add(foreign_score)
    db_session.commit()

    # Recovery query uses OR and surfaces this foreign score
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Criterion score evaluation or document mismatch",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_persisted_malformed_noncanonical_duplicate_chunk_ids_rejected_on_recovery(
    db_session,
) -> None:
    owner, doc, job, chunk = _setup_evaluation(db_session)
    valid_cid = str(chunk.chunk_id) if chunk else str(uuid4())

    results = make_scheduled_agent_results(
        job.evaluation_id, doc.document_id, partial_without_curriculum=False
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    sme_score = (
        db_session.query(StoredScore)
        .filter_by(evaluation_id=job.evaluation_id, criterion_id="OP-01")
        .one()
    )

    # 1. Non-canonical chunk ID (e.g. uppercase)
    sme_score.chunk_ids = json.dumps([valid_cid.upper()])
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError, match="Non-canonical chunk ID string"
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )

    # 2. Duplicate chunk IDs
    sme_score.chunk_ids = json.dumps([valid_cid, valid_cid])
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Duplicate chunk ID in criterion score",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_cross_evaluation_orphan_flag_rejected_on_recovery(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    results = make_scheduled_agent_results(
        job.evaluation_id, doc.document_id, partial_without_curriculum=False
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # Add orphan flag with foreign agent_result_id
    orphan_flag = EvaluationFlag(
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        agent_result_id=uuid4(),  # Foreign / non-existent result
        criterion_score_id=uuid4(),
        chunk_id=None,
        criterion_id="ITSO-01",
        score=3,
        reason="orphan flag",
    )
    db_session.add(orphan_flag)
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError,
        match="EvaluationFlag agent_result_id not in current results",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_advisory_raw_dict_and_invalid_types_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    # Raw dict instead of AdvisoryOutput is rejected
    bad_itso = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
    )
    object.__setattr__(
        bad_itso,
        "advisory_outputs",
        {"ungrounded_criteria": [{"criterion_id": "ITSO-01", "reason": "test"}]},
    )

    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        bad_itso,
    ]
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="advisory_outputs must be AdvisoryOutput or None",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_advisory_unknown_criterion_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    bad_itso = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        advisory_outputs=AdvisoryOutput(
            ungrounded_criteria=(
                UngroundedCriterionAdvisory(
                    criterion_id="UNKNOWN-CODE",
                    reason="Unknown code test",
                ),
            )
        ),
    )
    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        bad_itso,
    ]
    with pytest.raises(EvaluationResultIntegrityError, match="Unknown criterion"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_failed_advisory_leakage_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    bad_coord = make_agent_result(
        "coordinator",
        job.evaluation_id,
        doc.document_id,
        success=False,
    )
    # Inject advisory on failed result
    object.__setattr__(
        bad_coord,
        "advisory_outputs",
        AdvisoryOutput(
            ungrounded_criteria=(
                UngroundedCriterionAdvisory(
                    criterion_id="A-05", reason="failed leakage"
                ),
            )
        ),
    )

    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        bad_coord,
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Failed result must not contain raw response, prompt text, or advisory",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_failed_result_prompt_and_raw_leakage_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    # 1. raw_response leakage on failed result
    bad_coord_raw = make_agent_result(
        "coordinator",
        job.evaluation_id,
        doc.document_id,
        success=False,
    )
    object.__setattr__(bad_coord_raw, "raw_response", "{}")
    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        bad_coord_raw,
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Failed result must not contain raw response",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # 2. unsafe error message
    bad_coord_err = make_agent_result(
        "coordinator",
        job.evaluation_id,
        doc.document_id,
        success=False,
        error_message="unsafe unreferenced error message",
    )
    results[1] = bad_coord_err
    with pytest.raises(
        EvaluationResultIntegrityError, match="Invalid failure error_message format"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_nan_infinity_and_bounds_rejected_before_any_rows(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    # 1. NaN processing_seconds
    bad_sme = make_agent_result(
        "sme",
        job.evaluation_id,
        doc.document_id,
        processing_seconds=float("nan"),
    )
    results = [
        bad_sme,
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError, match="processing_seconds out of bounds"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    assert (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .count()
        == 0
    )

    # 2. Infinite subtotal
    bad_sme_sub = make_agent_result(
        "sme",
        job.evaluation_id,
        doc.document_id,
    )
    object.__setattr__(bad_sme_sub, "subtotal", float("inf"))
    results[0] = bad_sme_sub
    with pytest.raises(EvaluationResultIntegrityError, match="Invalid subtotal value"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # 3. Forged subtotal (not equal to mean of criteria)
    bad_sme_forged = make_agent_result(
        "sme",
        job.evaluation_id,
        doc.document_id,
    )
    object.__setattr__(bad_sme_forged, "subtotal", 1.0)  # criteria mean is 3.0
    results[0] = bad_sme_forged
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Subtotal mismatch against derived mean",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    assert (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .count()
        == 0
    )


def test_oversized_text_and_payloads_rejected_before_any_rows(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    # Oversized raw_response
    bad_sme = make_agent_result(
        "sme",
        job.evaluation_id,
        doc.document_id,
    )
    object.__setattr__(bad_sme, "raw_response", "x" * 130_000)
    results = [
        bad_sme,
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError, match="raw_response exceeded maximum bytes"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # Oversized prompt_text
    object.__setattr__(bad_sme, "raw_response", None)
    object.__setattr__(bad_sme, "prompt_text", "y" * 35_000)
    with pytest.raises(
        EvaluationResultIntegrityError, match="prompt_text exceeded maximum length"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_invalid_metadata_or_provenance_rejects_before_any_flush(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    # 1. Invalid metadata on 4th agent
    bad_itso_meta = make_agent_result("itso", job.evaluation_id, doc.document_id)
    object.__setattr__(bad_itso_meta, "metadata", "not-a-dict")

    results_meta = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        bad_itso_meta,
    ]
    with pytest.raises(EvaluationResultIntegrityError, match="metadata must be a dict"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results_meta,
            verify_ownership=lambda db: None,
        )
    assert (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .count()
        == 0
    )

    # 2. Invalid provenance on 3rd agent
    bad_gad_prov = make_agent_result(
        "gad",
        job.evaluation_id,
        doc.document_id,
        provenance=12345,  # type: ignore
    )
    results_prov = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        bad_gad_prov,
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError, match="provenance must be a dict or None"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results_prov,
            verify_ownership=lambda db: None,
        )
    assert (
        db_session.query(AgentResult)
        .filter(AgentResult.evaluation_id == job.evaluation_id)
        .count()
        == 0
    )


def test_internal_loader_defect_propagates_unwrapped(monkeypatch, db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)

    def boom_loader(*args, **kwargs):
        raise TypeError("internal programming defect")

    monkeypatch.setattr(
        "server.modules.synthesis.service.load_verified_evaluation_snapshots",
        boom_loader,
    )

    with pytest.raises(TypeError, match="internal programming defect"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_load_verified_persisted_agent_results_valid_and_recovery(db_session) -> None:
    owner, doc, job, chunk = _setup_evaluation(
        db_session, partial_without_curriculum=False
    )
    results = make_scheduled_agent_results(
        job.evaluation_id,
        doc.document_id,
        partial_without_curriculum=False,
        chunk_ids_by_criterion={"A-01": (str(chunk.chunk_id),)} if chunk else None,
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # Verification passes and returns rows in canonical order
    verified_rows = load_verified_persisted_agent_results(
        db_session, job.evaluation_id, doc.document_id
    )
    assert len(verified_rows) == 4
    assert [r.agent_name for r in verified_rows] == [
        "sme",
        "coordinator",
        "gad",
        "itso",
    ]


def test_load_verified_persisted_agent_results_rejects_null_snapshot_fk(
    db_session,
) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # Corrupt one row's form_snapshot_id to NULL
    row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    row.form_snapshot_id = None
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError, match="form_snapshot_id mismatch or NULL"
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_load_verified_persisted_results_rejects_mismatched_title_and_subtotal(
    db_session,
) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # 1. Corrupt criterion title in DB
    score_row = (
        db_session.query(StoredScore)
        .filter_by(evaluation_id=job.evaluation_id, criterion_id="A-05")
        .first()
    )
    original_title = score_row.criterion_title
    score_row.criterion_title = "Forged Title"
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError, match="Criterion title mismatch"
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )

    # Reset title and corrupt subtotal
    score_row.criterion_title = original_title
    agent_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="sme")
        .one()
    )
    agent_row.subtotal = 1.0  # actual is 3.0
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Subtotal mismatch against derived mean",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_legacy_agent_result_with_null_snapshot_id_remains_readable(
    db_session,
) -> None:
    """Historical rows with form_snapshot_id=NULL remain readable via results API."""
    owner, doc, job, _ = _setup_evaluation(db_session)
    db_session.query(EvaluationFormSnapshot).filter_by(
        evaluation_id=job.evaluation_id
    ).delete()

    # Manually insert legacy rows with form_snapshot_id=None
    result_row = AgentResult(
        agent_result_id=uuid4(),
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        agent_name="sme",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=100,
        model_name="legacy-model",
        summary="Legacy summary",
        success=True,
        form_snapshot_id=None,  # Legacy NULL
    )
    db_session.add(result_row)
    db_session.flush()

    score_row = StoredScore(
        criterion_score_id=uuid4(),
        agent_result_id=result_row.agent_result_id,
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        criterion_id="A-01",
        criterion_title="A-01 Title",
        score=3,
        justification="Legacy score",
    )
    db_session.add(score_row)
    job.status = EvaluationStatus.COMPLETED.value
    job.is_pre_snapshot_legacy = True
    db_session.commit()

    # Read via get_evaluation_results succeeds
    response = get_evaluation_results(job.evaluation_id, owner.user_id, db_session)
    assert response.evaluation_id == job.evaluation_id
    assert "sme" in response.domain_scores
    assert response.domain_scores["sme"].subtotal == 3.0

    # But recovery verifier rejects legacy NULL row
    with pytest.raises(EvaluationResultIntegrityError):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_aggregate_evidence_overflow_across_criteria_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    # 4 criteria each with 70 KiB evidence => aggregate ~280 KiB > 256 KiB
    big_chunk = "x" * 3500
    big_evidence = tuple([big_chunk] * 20)  # ~70 KiB evidence per criterion
    sme_result = make_agent_result(
        "sme",
        job.evaluation_id,
        doc.document_id,
        evidence_by_criterion={
            "OP-01": big_evidence,
            "OP-02": big_evidence,
            "OP-03": big_evidence,
            "OP-04": big_evidence,
        },
    )
    results = [
        sme_result,
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]

    with pytest.raises(
        EvaluationResultIntegrityError, match="Aggregate evidence JSON exceeded"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_malformed_criterion_item_and_id_produces_bounded_integrity_error(
    db_session,
) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)

    # 1. Non-InputCriterionScore item
    bad_sme_item = make_agent_result("sme", job.evaluation_id, doc.document_id)
    object.__setattr__(bad_sme_item, "criterion_scores", ("not-a-score",))
    results = [
        bad_sme_item,
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError, match="Invalid criterion score item type"
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )

    # 2. Untrimmed criterion_id
    bad_score = CriterionScore(
        criterion_id=" A-01 ", criterion_title="Title", score=3, justification="j"
    )
    scores = tuple(
        [bad_score]
        + [
            CriterionScore(
                criterion_id=c, criterion_title=f"{c} Title", score=3, justification="j"
            )
            for c in SEEDED_FIXTURE_CRITERION_CODES["sme"]
            if c != "A-01"
        ]
    )
    bad_sme_untrimmed = make_agent_result("sme", job.evaluation_id, doc.document_id)
    object.__setattr__(bad_sme_untrimmed, "criterion_scores", scores)
    results[0] = bad_sme_untrimmed
    with pytest.raises(EvaluationResultIntegrityError, match="Invalid criterion_id"):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_failed_group_payload_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    failed_coord = make_agent_result(
        "coordinator",
        job.evaluation_id,
        doc.document_id,
        success=False,
    )
    object.__setattr__(failed_coord, "metadata", {"group_prompts": {"k": "v"}})
    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        failed_coord,
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        make_agent_result("itso", job.evaluation_id, doc.document_id),
    ]
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Failed result must not contain group payloads",
    ):
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            doc.document_id,
            results,
            verify_ownership=lambda db: None,
        )


def test_persisted_unknown_non_finite_oversized_provenance_rejected(
    db_session,
) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # Corrupt persisted provenance to non-dict
    row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="sme")
        .one()
    )
    row.provenance = "not-a-dict"  # type: ignore
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError, match="Persisted provenance must be a dict"
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )

    row.provenance = {"unknown_key": "value"}
    db_session.commit()
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Persisted provenance does not match sanitized provenance",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )

    row.provenance = {"gad_extraction_seconds": float("nan")}
    db_session.commit()
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Non-finite numbers are not allowed",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )

    row.provenance = {"requested_model": "x" * 201}
    db_session.commit()
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Persisted provenance does not match sanitized provenance",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_failed_persisted_provenance_must_match_sanitized_value(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)
    results[1] = make_agent_result(
        "coordinator", job.evaluation_id, doc.document_id, success=False
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    failed_row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    failed_row.provenance = {"unknown_key": "secret"}
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Persisted provenance does not match sanitized provenance",
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_persisted_non_dict_group_map_rejected(db_session) -> None:
    owner, doc, job, _ = _setup_evaluation(db_session)
    results = make_scheduled_agent_results(job.evaluation_id, doc.document_id)
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="sme")
        .one()
    )
    row.group_prompts = ["not", "a", "dict"]  # type: ignore
    db_session.commit()

    with pytest.raises(
        EvaluationResultIntegrityError, match="Persisted group_prompts must be a dict"
    ):
        load_verified_persisted_agent_results(
            db_session, job.evaluation_id, doc.document_id
        )


def test_real_itso_producer_to_persistence_flow(db_session) -> None:
    """Producer-to-persistence test using real ITSO parser and DTOs."""
    import json

    from server.modules.agents.itso.response import (
        collect_advisory_outputs,
        criterion_scores,
        parse_response,
    )

    owner, doc, job, chunk = _setup_evaluation(db_session)
    valid_cid = str(chunk.chunk_id) if chunk else str(uuid4())

    # Representative raw ITSO response with shorthand score for ITSO-01 (ungrounded)
    # and full grounded structures for ITSO-02..05
    raw_itso_json = json.dumps(
        {
            "summary": "ITSO evaluation summary",
            "criterion_scores": {
                "ITSO-01": 3,
                "ITSO-02": {
                    "score": 4,
                    "justification": "grounded justification 2",
                    "chunk_ids": [valid_cid],
                    "evidence": ["evidence text 2"],
                },
                "ITSO-03": {
                    "score": 4,
                    "justification": "grounded justification 3",
                    "chunk_ids": [valid_cid],
                    "evidence": ["evidence text 3"],
                },
                "ITSO-04": {
                    "score": 4,
                    "justification": "grounded justification 4",
                    "chunk_ids": [valid_cid],
                    "evidence": ["evidence text 4"],
                },
                "ITSO-05": {
                    "score": 4,
                    "justification": "grounded justification 5",
                    "chunk_ids": [valid_cid],
                    "evidence": ["evidence text 5"],
                },
            },
        }
    )

    parsed = parse_response(raw_itso_json, known_chunk_ids=[valid_cid])
    itso_scores = criterion_scores(parsed, known_chunk_ids=[valid_cid])
    real_advisory = collect_advisory_outputs(parsed)

    assert real_advisory is not None
    assert isinstance(real_advisory, AdvisoryOutput)
    assert len(real_advisory.ungrounded_criteria) == 1
    assert real_advisory.ungrounded_criteria[0].criterion_id == "ITSO-01"

    derived_subtotal = sum(s.score for s in itso_scores) / len(itso_scores)
    itso_result = AgentEvaluationResult(
        agent_name="itso",
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        subtotal=derived_subtotal,
        criterion_scores=itso_scores,
        summary=parsed.get("summary", ""),
        model_name="itso-model",
        processing_seconds=1.0,
        token_count=100,
        success=True,
        advisory_outputs=real_advisory,
    )

    results = [
        make_agent_result("sme", job.evaluation_id, doc.document_id),
        make_agent_result("coordinator", job.evaluation_id, doc.document_id),
        make_agent_result("gad", job.evaluation_id, doc.document_id),
        itso_result,
    ]

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    verified_rows = load_verified_persisted_agent_results(
        db_session, job.evaluation_id, doc.document_id
    )
    itso_row = next(r for r in verified_rows if r.agent_name == "itso")
    assert itso_row.advisory_outputs == real_advisory.to_dict()

    itso_score_1 = (
        db_session.query(StoredScore)
        .filter_by(evaluation_id=job.evaluation_id, criterion_id="ITSO-01")
        .one()
    )
    assert itso_score_1.justification == ""

    flag = (
        db_session.query(EvaluationFlag)
        .filter_by(
            evaluation_id=job.evaluation_id,
            agent_result_id=itso_row.agent_result_id,
            criterion_id="ITSO-01",
        )
        .one()
    )
    assert flag.chunk_id is None
    assert flag.score == 3
    assert flag.reason == real_advisory.ungrounded_criteria[0].reason


def test_orchestrator_recovery_rejects_null_snapshot_and_fails_job_without_rerun(
    db_session, monkeypatch
) -> None:
    """Orchestrator recovery fails closed when persisted row has NULL snapshot ID."""
    from server.core import database as core_database
    from server.modules.evaluations.exceptions import EvaluationPipelineFailure
    from server.modules.evaluations.orchestrator import _execute_claimed_evaluation
    from server.modules.evaluations.service import acquire_evaluation_execution
    from server.modules.synthesis.models import MonitoringMatrix
    from sqlalchemy.orm import sessionmaker

    owner, doc, job, _ = _setup_evaluation(db_session, partial_without_curriculum=False)

    results = make_scheduled_agent_results(
        job.evaluation_id, doc.document_id, partial_without_curriculum=False
    )
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        results,
        verify_ownership=lambda db: None,
    )

    # Corrupt one row's form_snapshot_id to NULL
    row = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
        .one()
    )
    row.form_snapshot_id = None
    job.status = EvaluationStatus.SUBMITTED.value
    job.execution_token = None
    job.admission_slot = None
    db_session.commit()

    supervisor_called = False

    def explode_if_supervisor_called(*args, **kwargs):
        nonlocal supervisor_called
        supervisor_called = True
        raise AssertionError("Supervisor must NOT be rerun during recovery")

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator.Supervisor.run_evaluation",
        explode_if_supervisor_called,
    )

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    token = uuid4()
    assert acquire_evaluation_execution(db_session, job.evaluation_id, token)
    db_session.commit()

    with pytest.raises(EvaluationPipelineFailure):
        _execute_claimed_evaluation(
            job.evaluation_id,
            execution_token=token,
            db_session_factory=session_factory,
        )

    assert supervisor_called is False
    db_session.expire_all()
    refreshed_job = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed_job.status == EvaluationStatus.FAILED.value
    matrix = (
        db_session.query(MonitoringMatrix)
        .filter_by(evaluation_id=job.evaluation_id)
        .one()
    )
    assert matrix.evaluation_status == "FAILED"


def test_dispatch_sanitizer_clears_prompt_text_and_fits_persistence_contract(
    db_session,
) -> None:
    """Sanitizer in dispatch strips prompt, raw, advisory, groups for failed results."""
    from server.modules.agents.supervision.dispatch import AgentDispatcher
    from server.modules.synthesis.result_integrity import build_persistable_agent_result

    owner, doc, job, _ = _setup_evaluation(db_session)
    from server.modules.rubrics.snapshots import load_verified_evaluation_snapshots

    snapshots = load_verified_evaluation_snapshots(
        db_session, job.evaluation_id, ("sme", "coordinator", "gad", "itso")
    )
    coord_snapshot = next(s for s in snapshots if s.agent_id == "coordinator")

    # Dirty returned failed result
    dirty_failure = AgentEvaluationResult(
        agent_name="coordinator",
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        subtotal=2.5,
        criterion_scores=(CriterionScore("A-05", "Title", 3, "justification"),),
        summary="Some dirty summary",
        model_name="coordinator-model",
        processing_seconds=1.5,
        token_count=500,
        success=False,
        error_message="CoordinatorLLMTimeout (reference: a1b2c3d4e5f60718)",
        raw_response='{"raw": "response"}',
        prompt_text="sensitive prompt text",
        metadata={"group_prompts": {"k": "v"}, "group_responses": {"k": "v"}},
        advisory_outputs=AdvisoryOutput(
            ungrounded_criteria=(
                UngroundedCriterionAdvisory(criterion_id="A-05", reason="r"),
            )
        ),
        provenance={"api_key": "secret", "precheck_version": "1"},
    )

    sanitized = AgentDispatcher._sanitize_returned_failure(dirty_failure)
    assert sanitized.subtotal == 0.0
    assert sanitized.criterion_scores == ()
    assert sanitized.summary == ""
    assert sanitized.token_count == 0
    assert sanitized.raw_response is None
    assert sanitized.prompt_text is None
    assert sanitized.metadata == {}
    assert sanitized.advisory_outputs is None
    assert (
        sanitized.error_message == "CoordinatorLLMTimeout (reference: a1b2c3d4e5f60718)"
    )
    assert sanitized.provenance == {"precheck_version": "1"}

    # Sanitized result must cleanly build into persistable envelope
    persistable = build_persistable_agent_result(sanitized, coord_snapshot)
    assert persistable.success is False
    assert persistable.subtotal == 0.0
    assert persistable.token_count == 0
    assert persistable.summary == ""
    assert persistable.prompt_text is None
    assert persistable.raw_response is None
    assert persistable.group_prompts_json is None
    assert persistable.group_responses_json is None
    assert persistable.advisory_outputs_json is None
    assert (
        persistable.error_message
        == "CoordinatorLLMTimeout (reference: a1b2c3d4e5f60718)"
    )


def test_itso_success_rejects_prompt_text_or_raw_response_persistence(
    db_session,
) -> None:
    """ITSO successful persistable result rejects non-None prompt_text/raw_response."""
    from server.modules.rubrics.snapshots import load_verified_evaluation_snapshots
    from server.modules.synthesis.result_integrity import build_persistable_agent_result

    owner, doc, job, chunk = _setup_evaluation(db_session)
    valid_cid = str(chunk.chunk_id) if chunk else str(uuid4())

    snapshots = load_verified_evaluation_snapshots(
        db_session,
        job.evaluation_id,
        ("sme", "coordinator", "gad", "itso"),
    )
    itso_snapshot = next(s for s in snapshots if s.agent_id == "itso")
    assert itso_snapshot is not None

    itso_res = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        chunk_ids_by_criterion={
            c: (valid_cid,) for c in SEEDED_FIXTURE_CRITERION_CODES["itso"]
        },
        evidence_by_criterion={
            c: ("ev",) for c in SEEDED_FIXTURE_CRITERION_CODES["itso"]
        },
    )
    # Default make_agent_result has prompt_text=None and raw_response=None -> succeeds
    persistable = build_persistable_agent_result(itso_res, itso_snapshot)
    assert persistable.prompt_text is None
    assert persistable.raw_response is None

    # Tampered prompt_text fails
    bad_prompt_itso = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        chunk_ids_by_criterion={
            c: (valid_cid,) for c in SEEDED_FIXTURE_CRITERION_CODES["itso"]
        },
        evidence_by_criterion={
            c: ("ev",) for c in SEEDED_FIXTURE_CRITERION_CODES["itso"]
        },
    )
    object.__setattr__(bad_prompt_itso, "prompt_text", "unauthorized_prompt_text")
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Successful ITSO result must not contain raw_response or prompt_text",
    ):
        build_persistable_agent_result(bad_prompt_itso, itso_snapshot)

    # Tampered raw_response fails
    bad_raw_itso = make_agent_result(
        "itso",
        job.evaluation_id,
        doc.document_id,
        chunk_ids_by_criterion={
            c: (valid_cid,) for c in SEEDED_FIXTURE_CRITERION_CODES["itso"]
        },
        evidence_by_criterion={
            c: ("ev",) for c in SEEDED_FIXTURE_CRITERION_CODES["itso"]
        },
    )
    object.__setattr__(bad_raw_itso, "raw_response", '{"raw": "response"}')
    with pytest.raises(
        EvaluationResultIntegrityError,
        match="Successful ITSO result must not contain raw_response or prompt_text",
    ):
        build_persistable_agent_result(bad_raw_itso, itso_snapshot)
