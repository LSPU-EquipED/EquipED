"""Rubric loading helpers for relational rubric storage."""

from __future__ import annotations

import uuid
from typing import Any

from server.core.database import get_db_session, get_session_factory

from .models import RubricCriterion, RubricDomain, RubricSet


def resolve_rubric_agent_id(source_type: str) -> str:
    """Map a rubric source type to the matching rubric agent_id."""

    if source_type == "rubric_coord":
        return "coordinator"
    if source_type.startswith("rubric_"):
        return source_type.removeprefix("rubric_")
    return source_type


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

        # Single query for all criteria in this rubric set (avoids N+1).
        all_criteria = (
            session.query(RubricCriterion)
            .join(RubricDomain, RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id)
            .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
            .order_by(
                RubricDomain.display_order.asc(),
                RubricDomain.code.asc(),
                RubricCriterion.display_order.asc(),
                RubricCriterion.criterion_code.asc(),
            )
            .all()
        )
        # Group criteria by domain_id for O(1) lookup during formatting.
        criteria_by_domain: dict[uuid.UUID, list[RubricCriterion]] = {}
        for criterion in all_criteria:
            criteria_by_domain.setdefault(criterion.rubric_domain_id, []).append(criterion)

        context: list[str] = [
            f"[{rubric_set.name}]",
            f"Agent: {rubric_set.agent_id}",
            f"Version: {rubric_set.version_number}",
        ]
        for domain in domains:
            context.append(f"Domain: {domain.title}")
            for criterion in criteria_by_domain.get(domain.rubric_domain_id, []):
                context.append(
                    f"{criterion.criterion_code} | Title: {criterion.title} | Description: {criterion.description}"
                )
        return context
    finally:
        if close_session:
            session.close()


def get_active_rubric_criteria(agent_id: str, db: Any | None = None) -> dict[str, str]:
    """Return ``{criterion_code: title}`` for the active rubric set.

    Mirrors ``get_active_rubric_context``'s query but returns structured
    code/title pairs instead of formatted prompt strings, for callers that
    need criterion titles without asking the LLM to echo them back (e.g. SME,
    which scores criteria via the code-side engine rather than a prompt).
    Returns ``{}`` if no active rubric set exists.
    """

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
            return {}

        criteria = (
            session.query(RubricCriterion)
            .join(
                RubricDomain,
                RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
            )
            .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
            .order_by(
                RubricDomain.display_order.asc(),
                RubricDomain.code.asc(),
                RubricCriterion.display_order.asc(),
                RubricCriterion.criterion_code.asc(),
            )
            .all()
        )
        return {criterion.criterion_code: criterion.title for criterion in criteria}
    finally:
        if close_session:
            session.close()


def get_active_rubric_descriptions(
    agent_id: str, db: Any | None = None
) -> dict[str, str]:
    """Return ``{criterion_code: description}`` for the active rubric set.

    Mirrors ``get_active_rubric_criteria`` but returns descriptions instead
    of titles, for callers that build LLM prompts from rubric text (e.g. the
    grouped-scoring prompt builders) rather than hardcoding it in Python.
    Returns ``{}`` if no active rubric set exists.
    """

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
            return {}

        criteria = (
            session.query(RubricCriterion)
            .join(
                RubricDomain,
                RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
            )
            .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
            .order_by(
                RubricDomain.display_order.asc(),
                RubricDomain.code.asc(),
                RubricCriterion.display_order.asc(),
                RubricCriterion.criterion_code.asc(),
            )
            .all()
        )
        return {
            criterion.criterion_code: criterion.description for criterion in criteria
        }
    finally:
        if close_session:
            session.close()


__all__ = [
    "get_active_rubric_context",
    "get_active_rubric_criteria",
    "get_active_rubric_descriptions",
    "resolve_rubric_agent_id",
]
