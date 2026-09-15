"""System-wide metric helpers for the admin dashboard."""

from __future__ import annotations

from typing import Any

from server.modules.auth.models import User, UserRole
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from sqlalchemy import func

__all__ = ["get_system_summary"]

_TERMINAL_STATUSES = {
    EvaluationStatus.COMPLETED.value,
    EvaluationStatus.FAILED.value,
}


def get_system_summary(db: Any) -> dict[str, int]:
    """Return system-wide counts for the admin dashboard."""
    from server.modules.documents.models import Document

    total_documents = db.query(func.count()).select_from(Document).scalar() or 0

    total_faculty = (
        db.query(func.count())
        .select_from(User)
        .filter(User.role == UserRole.FACULTY)
        .scalar()
        or 0
    )

    active_evaluations = (
        db.query(func.count())
        .select_from(EvaluationJob)
        .filter(EvaluationJob.status.not_in(_TERMINAL_STATUSES))
        .scalar()
        or 0
    )

    failed_evaluations = (
        db.query(func.count())
        .select_from(EvaluationJob)
        .filter(EvaluationJob.status == EvaluationStatus.FAILED.value)
        .scalar()
        or 0
    )

    return {
        "total_documents": total_documents,
        "total_faculty": total_faculty,
        "active_evaluations": active_evaluations,
        "failed_evaluations": failed_evaluations,
    }
