"""Explicit exclusion until an evidence-review training contract is approved."""

from sqlalchemy.orm import Session


def reject_itso_v2_export(db, *, agent_id, evaluation_id=None, since=None, until=None):
    if agent_id != "itso" or not isinstance(db, Session):
        return
    from server.modules.itso_assessments.service import has_assessments

    if has_assessments(db, evaluation_id=evaluation_id, since=since, until=until):
        raise ValueError(
            "unsupported_version: ITSO-v2 training export is not supported"
        )
