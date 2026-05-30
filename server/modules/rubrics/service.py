"""Rubric loading helpers for relational rubric storage."""

from __future__ import annotations

from typing import Any

from server.core.database import get_db_session, get_session_factory

from .models import RubricCriterion, RubricDomain, RubricSet


def get_active_rubric_context(agent_id: str, db: Any | None = None) -> list[str]:
    """Return formatted rubric context for the active rubric set."""

    session = db or get_session_factory()()
    close_session = db is None
    try:
        rubric_set = (
            session.query(RubricSet)
            .filter_by(agent_id=agent_id, status="active")
            .order_by(RubricSet.version_number.desc())
            .first()
        )
        if rubric_set is None:
            return []

        domains = (
            session.query(RubricDomain)
            .filter_by(rubric_set_id=rubric_set.rubric_set_id)
            .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
            .all()
        )

        context: list[str] = [
            f"[{rubric_set.name}]",
            f"Agent: {rubric_set.agent_id}",
            f"Version: {rubric_set.version_number}",
        ]
        for domain in domains:
            context.append(f"Domain: {domain.title}")
            criteria = (
                session.query(RubricCriterion)
                .filter_by(rubric_domain_id=domain.rubric_domain_id)
                .order_by(RubricCriterion.display_order.asc(), RubricCriterion.criterion_code.asc())
                .all()
            )
            for criterion in criteria:
                context.append(
                    f"{criterion.criterion_code} | Title: {criterion.title} | Description: {criterion.description}"
                )
        return context
    finally:
        if close_session:
            session.close()


__all__ = ["get_active_rubric_context"]
