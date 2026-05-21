"""Feedback service for preference logging and querying."""

from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from .models import PreferenceLog


def list_preference_logs(
    db: Session,
    action: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PreferenceLog], int]:
    """Return paginated preference logs, optionally filtered by action."""

    query = db.query(PreferenceLog)
    if action:
        query = query.filter(PreferenceLog.action == action.upper())
    total = query.count()
    items = (
        query.order_by(desc(PreferenceLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total
