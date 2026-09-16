"""Database mutations and CAS transitions for syllabus alignment runs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from server.core.config import get_settings
from server.modules.syllabus_alignment.models import (
    SyllabusAlignmentLevel,
    SyllabusAlignmentRun,
    SyllabusAlignmentStatus,
)
from sqlalchemy.exc import IntegrityError

ACTIVE_STATUSES = (
    SyllabusAlignmentStatus.QUEUED.value,
    SyllabusAlignmentStatus.RUNNING.value,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def create_or_reset_queued_run(
    db: Any,
    *,
    slm_document_id: uuid.UUID,
    syllabus_document_id: uuid.UUID,
    requested_by: uuid.UUID,
) -> tuple[SyllabusAlignmentRun, bool]:
    """Create or reset a queued run under row lock.

    Returns (run, was_created_or_reset). If an existing run is already ACTIVE,
    was_created_or_reset will be False and the existing run is returned as-is.
    """
    existing = (
        db.query(SyllabusAlignmentRun)
        .filter(
            SyllabusAlignmentRun.slm_document_id == slm_document_id,
            SyllabusAlignmentRun.requested_by == requested_by,
        )
        .with_for_update()
        .first()
    )
    if existing is not None and existing.status in ACTIVE_STATUSES:
        return existing, False

    model_name = get_settings().get_agent_model("sme")
    now = utc_now()
    if existing is None:
        run = SyllabusAlignmentRun(
            alignment_id=uuid.uuid4(),
            slm_document_id=slm_document_id,
            syllabus_document_id=syllabus_document_id,
            requested_by=requested_by,
            status=SyllabusAlignmentStatus.QUEUED.value,
            model_name=model_name,
            provenance={"agent_configuration": "sme", "requested_model": model_name},
            created_at=now,
            updated_at=now,
        )
        db.add(run)
    else:
        run = existing
        run.syllabus_document_id = syllabus_document_id
        run.status = SyllabusAlignmentStatus.QUEUED.value
        run.alignment_level = None
        run.justification = None
        run.alignment_artifact = None
        run.model_name = model_name
        run.provenance = {
            "agent_configuration": "sme",
            "requested_model": model_name,
        }
        run.error_message = None
        run.created_at = now
        run.started_at = None
        run.completed_at = None
        run.updated_at = now

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active = (
            db.query(SyllabusAlignmentRun)
            .filter(
                SyllabusAlignmentRun.slm_document_id == slm_document_id,
                SyllabusAlignmentRun.requested_by == requested_by,
            )
            .first()
        )
        if active is None:
            raise
        return active, False

    db.refresh(run)
    return run, True


def claim_queued_run_cas(session: Any, alignment_id: uuid.UUID) -> bool:
    """Compare-and-swap claim: transition status QUEUED -> RUNNING.

    Returns True if successfully claimed (count == 1).
    """
    claimed_at = utc_now()
    claimed = (
        session.query(SyllabusAlignmentRun)
        .filter(
            SyllabusAlignmentRun.alignment_id == alignment_id,
            SyllabusAlignmentRun.status == SyllabusAlignmentStatus.QUEUED.value,
        )
        .update(
            {
                SyllabusAlignmentRun.status: SyllabusAlignmentStatus.RUNNING.value,
                SyllabusAlignmentRun.started_at: claimed_at,
                SyllabusAlignmentRun.updated_at: claimed_at,
            },
            synchronize_session=False,
        )
    )
    session.commit()
    return claimed == 1


def mark_run_completed(
    session: Any,
    alignment_id: uuid.UUID,
    *,
    model_name: str | None,
    result: dict[str, Any],
) -> None:
    """Transition run to COMPLETED or FAILED (if level UNAVAILABLE)."""
    run = session.get(SyllabusAlignmentRun, alignment_id)
    if run is None:
        return
    run.model_name = model_name or run.model_name
    run.justification = str(result.get("statement") or "").strip()
    run.alignment_artifact = result
    now = utc_now()
    run.completed_at = now
    run.updated_at = now
    level = str(result.get("status", "UNAVAILABLE"))
    if level == SyllabusAlignmentLevel.UNAVAILABLE.value:
        run.status = SyllabusAlignmentStatus.FAILED.value
        run.alignment_level = SyllabusAlignmentLevel.UNAVAILABLE.value
        run.error_message = (
            run.justification or "Alignment analysis was unavailable."
        )
    else:
        run.status = SyllabusAlignmentStatus.COMPLETED.value
        run.alignment_level = level
        run.error_message = None
    session.commit()


def mark_run_failed(
    session: Any,
    alignment_id: uuid.UUID,
    *,
    error_message: str,
    justification: str,
) -> None:
    """Mark run as FAILED with safe failure text."""
    failed = session.get(SyllabusAlignmentRun, alignment_id)
    if failed is not None:
        now = utc_now()
        failed.status = SyllabusAlignmentStatus.FAILED.value
        failed.alignment_level = SyllabusAlignmentLevel.UNAVAILABLE.value
        failed.justification = justification
        failed.error_message = error_message
        failed.completed_at = now
        failed.updated_at = now
        session.commit()


def mark_interrupted_runs_failed(session: Any) -> int:
    """Fail active QUEUED/RUNNING runs across app restart."""
    now = utc_now()
    rows = (
        session.query(SyllabusAlignmentRun)
        .filter(SyllabusAlignmentRun.status.in_(ACTIVE_STATUSES))
        .all()
    )
    for run in rows:
        run.status = SyllabusAlignmentStatus.FAILED.value
        run.alignment_level = SyllabusAlignmentLevel.UNAVAILABLE.value
        run.justification = (
            "The alignment run was interrupted by an application restart. "
            "Start a new run to retry."
        )
        run.error_message = (
            "Background alignment interrupted by application restart."
        )
        run.completed_at = now
        run.updated_at = now
    session.commit()
    return len(rows)


__all__ = [
    "ACTIVE_STATUSES",
    "utc_now",
    "create_or_reset_queued_run",
    "claim_queued_run_cas",
    "mark_run_completed",
    "mark_run_failed",
    "mark_interrupted_runs_failed",
]
