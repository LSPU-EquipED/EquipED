"""Explicit exclusion until an evidence-review training contract is approved."""

from sqlalchemy import select
from sqlalchemy.orm import Session


def reject_itso_v2_export(db, *, agent_id, evaluation_id=None, since=None, until=None):
    if agent_id != "itso" or not isinstance(db, Session):
        return
    from server.modules.evaluations.itso.models import ITSOAssessment

    query = select(ITSOAssessment.assessment_id)
    if evaluation_id is not None:
        query = query.where(ITSOAssessment.evaluation_id == evaluation_id)
    if since is not None:
        query = query.where(ITSOAssessment.created_at >= since)
    if until is not None:
        query = query.where(ITSOAssessment.created_at <= until)
    if db.scalar(query.limit(1)) is not None:
        raise ValueError(
            "unsupported_version: ITSO-v2 training export is not supported"
        )
