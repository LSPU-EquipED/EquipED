"""Command orchestration for creating standalone syllabus alignment runs."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from server.modules.syllabus_alignment.admission import (
    validate_syllabus_alignment_targets,
)
from server.modules.syllabus_alignment.jobs import run_syllabus_alignment_job
from server.modules.syllabus_alignment.queries import to_run_response
from server.modules.syllabus_alignment.repository import create_or_reset_queued_run
from server.modules.syllabus_alignment.schemas import SyllabusAlignmentRunResponse


def create_syllabus_alignment(
    db: Any,
    *,
    slm_document_id: uuid.UUID,
    syllabus_document_id: uuid.UUID,
    requested_by: uuid.UUID,
    background_tasks: Any | None = None,
    schedule_job: Callable[[uuid.UUID], None] | None = None,
) -> SyllabusAlignmentRunResponse:
    """Validate direct inputs, queue independent run, and schedule job."""
    validate_syllabus_alignment_targets(
        db,
        slm_document_id=slm_document_id,
        syllabus_document_id=syllabus_document_id,
        owner_id=requested_by,
    )

    run, was_queued = create_or_reset_queued_run(
        db,
        slm_document_id=slm_document_id,
        syllabus_document_id=syllabus_document_id,
        requested_by=requested_by,
    )

    if was_queued:
        if schedule_job is not None:
            schedule_job(run.alignment_id)
        elif background_tasks is not None:
            background_tasks.add_task(run_syllabus_alignment_job, run.alignment_id)

    return to_run_response(db, run)


__all__ = [
    "create_syllabus_alignment",
]
