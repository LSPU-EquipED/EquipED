"""Tests for feedback state reduction and effective reviewer corrections."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.auth.models import User, UserRole
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.feedback.state import (
    EffectiveCriterionCorrection,
    get_effective_criterion_corrections,
    get_effective_criterion_corrections_batch,
)


def _setup_job(db_session):
    uid = uuid4()
    user = User(
        user_id=uid,
        name="Evaluator",
        email=f"eval-{uid}@lspu.edu.ph",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.flush()

    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=user.user_id,
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
        submitted_by=user.user_id,
    )
    db_session.add(job)
    db_session.flush()
    return job, user


def test_latest_edit_returns_typed_correction(db_session):
    job, user = _setup_job(db_session)
    log_id = uuid4()
    db_session.add(
        PreferenceLog(
            log_id=log_id,
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="EDIT",
            edited_json={"score": 3, "justification": "Updated explanation"},
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    corrections = get_effective_criterion_corrections(db_session, job.evaluation_id)
    assert ("itso", "itso-01") in corrections
    corr = corrections[("itso", "itso-01")]
    assert isinstance(corr, EffectiveCriterionCorrection)
    assert corr.log_id == log_id
    assert corr.evaluation_id == job.evaluation_id
    assert corr.agent_name == "itso"
    assert corr.criterion_id == "itso-01"
    assert corr.action == "EDIT"
    assert corr.score == 3
    assert corr.justification == "Updated explanation"
    assert corr.user_id == user.user_id


def test_latest_reject_returns_correction_without_score(db_session):
    job, user = _setup_job(db_session)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="sme",
            criterion_id="A-02",
            action="REJECT",
            notes="Bad evaluation",
        )
    )
    db_session.commit()

    corrections = get_effective_criterion_corrections(db_session, job.evaluation_id)
    assert ("sme", "A-02") in corrections
    corr = corrections[("sme", "A-02")]
    assert corr.action == "REJECT"
    assert corr.score is None
    assert corr.justification is None


def test_accept_superseding_earlier_edit_clears_overlay(db_session):
    job, user = _setup_job(db_session)
    # Earlier EDIT
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={"score": 2, "justification": "First edit"},
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    )
    # Later ACCEPT
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="ACCEPT",
            created_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    corrections = get_effective_criterion_corrections(db_session, job.evaluation_id)
    assert ("itso", "itso-02") not in corrections


def test_accept_superseding_earlier_reject_clears_overlay(db_session):
    job, user = _setup_job(db_session)
    # Earlier REJECT
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="REJECT",
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    )
    # Later ACCEPT
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="ACCEPT",
            created_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    corrections = get_effective_criterion_corrections(db_session, job.evaluation_id)
    assert ("sme", "A-01") not in corrections


def test_edit_superseding_earlier_accept_creates_overlay(db_session):
    job, user = _setup_job(db_session)
    # Earlier ACCEPT
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="itso",
            criterion_id="itso-03",
            action="ACCEPT",
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    )
    # Later EDIT
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="itso",
            criterion_id="itso-03",
            action="EDIT",
            edited_json={"score": 4, "justification": "Changed mind to edit"},
            created_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    corrections = get_effective_criterion_corrections(db_session, job.evaluation_id)
    assert ("itso", "itso-03") in corrections
    assert corrections[("itso", "itso-03")].action == "EDIT"
    assert corrections[("itso", "itso-03")].score == 4


def test_timestamp_tie_determinism(db_session):
    job, user = _setup_job(db_session)
    same_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    id_lower = uuid4()
    id_higher = uuid4()
    if id_lower > id_higher:
        id_lower, id_higher = id_higher, id_lower

    # Add lower ID log (EDIT score 1) and higher ID log (EDIT score 4)
    # with same timestamp.
    db_session.add(
        PreferenceLog(
            log_id=id_lower,
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="EDIT",
            edited_json={"score": 1, "justification": "Lower id"},
            created_at=same_time,
        )
    )
    db_session.add(
        PreferenceLog(
            log_id=id_higher,
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="EDIT",
            edited_json={"score": 4, "justification": "Higher id"},
            created_at=same_time,
        )
    )
    db_session.commit()

    corrections = get_effective_criterion_corrections(db_session, job.evaluation_id)
    assert ("itso", "itso-01") in corrections
    # Must deterministically select higher ID due to created_at DESC, log_id DESC
    assert corrections[("itso", "itso-01")].log_id == id_higher
    assert corrections[("itso", "itso-01")].score == 4


def test_filter_by_agent_names(db_session):
    job, user = _setup_job(db_session)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="EDIT",
            edited_json={"score": 3, "justification": "ITSO edit"},
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=user.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 2, "justification": "SME edit"},
        )
    )
    db_session.commit()

    itso_only = get_effective_criterion_corrections(
        db_session, job.evaluation_id, agent_names=["itso"]
    )
    assert ("itso", "itso-01") in itso_only
    assert ("sme", "A-01") not in itso_only


def test_batch_corrections_resolves_multiple_evaluations_and_actions(db_session):
    job1, user1 = _setup_job(db_session)
    job2, user2 = _setup_job(db_session)

    # Job 1: EDIT on itso-01, REJECT on itso-02, ACCEPT superseding EDIT on itso-03
    db_session.add(
        PreferenceLog(
            evaluation_id=job1.evaluation_id,
            user_id=user1.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="EDIT",
            edited_json={"score": 4, "justification": "Job 1 edit"},
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job1.evaluation_id,
            user_id=user1.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="REJECT",
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job1.evaluation_id,
            user_id=user1.user_id,
            agent_name="itso",
            criterion_id="itso-03",
            action="EDIT",
            edited_json={"score": 1, "justification": "Old edit"},
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job1.evaluation_id,
            user_id=user1.user_id,
            agent_name="itso",
            criterion_id="itso-03",
            action="ACCEPT",
            created_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
        )
    )

    # Job 2: EDIT on A-01 (sme), EDIT on itso-01 (itso)
    db_session.add(
        PreferenceLog(
            evaluation_id=job2.evaluation_id,
            user_id=user2.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 2, "justification": "Job 2 SME edit"},
            created_at=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job2.evaluation_id,
            user_id=user2.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="EDIT",
            edited_json={"score": 3, "justification": "Job 2 ITSO edit"},
            created_at=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    # Batch resolve for both jobs
    batch = get_effective_criterion_corrections_batch(
        db_session, [job1.evaluation_id, job2.evaluation_id]
    )

    # Job 1 assertions
    assert job1.evaluation_id in batch
    job1_corr = batch[job1.evaluation_id]
    assert ("itso", "itso-01") in job1_corr
    assert job1_corr[("itso", "itso-01")].action == "EDIT"
    assert job1_corr[("itso", "itso-01")].score == 4
    assert ("itso", "itso-02") in job1_corr
    assert job1_corr[("itso", "itso-02")].action == "REJECT"
    assert ("itso", "itso-03") not in job1_corr  # Retracted by ACCEPT

    # Job 2 assertions
    assert job2.evaluation_id in batch
    job2_corr = batch[job2.evaluation_id]
    assert ("sme", "A-01") in job2_corr
    assert job2_corr[("sme", "A-01")].score == 2
    assert ("itso", "itso-01") in job2_corr
    assert job2_corr[("itso", "itso-01")].score == 3

    # Batch with agent filter
    itso_batch = get_effective_criterion_corrections_batch(
        db_session,
        [job1.evaluation_id, job2.evaluation_id],
        agent_names=["itso"],
    )
    assert ("sme", "A-01") not in itso_batch.get(job2.evaluation_id, {})
    assert ("itso", "itso-01") in itso_batch.get(job2.evaluation_id, {})


def test_batch_corrections_empty_input_returns_empty_dict(db_session):
    assert get_effective_criterion_corrections_batch(db_session, []) == {}
    assert get_effective_criterion_corrections_batch(db_session, [None]) == {}  # type: ignore[list-item]


def test_batch_corrections_timestamp_tie_determinism(db_session):
    job1, user1 = _setup_job(db_session)
    job2, user2 = _setup_job(db_session)
    same_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    # Job 1 tie
    id1_lower = uuid4()
    id1_higher = uuid4()
    if id1_lower > id1_higher:
        id1_lower, id1_higher = id1_higher, id1_lower
    db_session.add(
        PreferenceLog(
            log_id=id1_lower,
            evaluation_id=job1.evaluation_id,
            user_id=user1.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="EDIT",
            edited_json={"score": 1, "justification": "Job 1 low id"},
            created_at=same_time,
        )
    )
    db_session.add(
        PreferenceLog(
            log_id=id1_higher,
            evaluation_id=job1.evaluation_id,
            user_id=user1.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="EDIT",
            edited_json={"score": 4, "justification": "Job 1 high id"},
            created_at=same_time,
        )
    )

    # Job 2 tie
    id2_lower = uuid4()
    id2_higher = uuid4()
    if id2_lower > id2_higher:
        id2_lower, id2_higher = id2_higher, id2_lower
    db_session.add(
        PreferenceLog(
            log_id=id2_lower,
            evaluation_id=job2.evaluation_id,
            user_id=user2.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 1, "justification": "Job 2 low id"},
            created_at=same_time,
        )
    )
    db_session.add(
        PreferenceLog(
            log_id=id2_higher,
            evaluation_id=job2.evaluation_id,
            user_id=user2.user_id,
            agent_name="sme",
            criterion_id="A-01",
            action="EDIT",
            edited_json={"score": 3, "justification": "Job 2 high id"},
            created_at=same_time,
        )
    )
    db_session.commit()

    batch = get_effective_criterion_corrections_batch(
        db_session, [job1.evaluation_id, job2.evaluation_id]
    )
    assert batch[job1.evaluation_id][("itso", "itso-01")].log_id == id1_higher
    assert batch[job1.evaluation_id][("itso", "itso-01")].score == 4
    assert batch[job2.evaluation_id][("sme", "A-01")].log_id == id2_higher
    assert batch[job2.evaluation_id][("sme", "A-01")].score == 3
