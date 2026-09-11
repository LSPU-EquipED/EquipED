"""Active rubric loading and runtime scoring context for specialist agents."""

from __future__ import annotations

import uuid
from typing import Any

from server.core.database import get_session_factory

from .models import RubricAgentActivation, RubricCriterion, RubricDomain, RubricSet


def _get_active_rubric_set(session: Any, agent_id: str) -> RubricSet | None:
    """Resolve active rubric set for an agent via activation pointer (sole authority).

    Fails closed (returns None) if no activation exists, if the pointed RubricSet
    is missing, if the pointed RubricSet agent_id mismatches, or if status is not
    'published'. Never falls back to legacy/latest published guessing.
    """
    activation = (
        session.query(RubricAgentActivation).filter_by(agent_id=agent_id).one_or_none()
    )
    if activation is None:
        return None

    rubric_set = (
        session.query(RubricSet)
        .filter_by(rubric_set_id=activation.rubric_set_id)
        .one_or_none()
    )
    if (
        rubric_set is None
        or rubric_set.agent_id != agent_id
        or rubric_set.status != "published"
    ):
        return None
    return rubric_set


def get_active_rubric_context(agent_id: str, db: Any | None = None) -> list[str]:
    """Return formatted rubric context for the active rubric set."""
    session = db or get_session_factory()()
    close_session = db is None
    try:
        rubric_set = _get_active_rubric_set(session, agent_id)
        if rubric_set is None:
            return []

        domains = (
            session.query(RubricDomain)
            .filter_by(rubric_set_id=rubric_set.rubric_set_id)
            .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
            .all()
        )

        all_criteria = (
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
        criteria_by_domain: dict[uuid.UUID, list[RubricCriterion]] = {}
        for criterion in all_criteria:
            criteria_by_domain.setdefault(criterion.rubric_domain_id, []).append(
                criterion
            )

        context: list[str] = [
            f"[{rubric_set.name}]",
            f"Agent: {rubric_set.agent_id}",
            f"Version: {rubric_set.version_number}",
        ]
        for domain in domains:
            context.append(f"Domain: {domain.title}")
            for criterion in criteria_by_domain.get(domain.rubric_domain_id, []):
                context.append(
                    f"{criterion.criterion_code} | "
                    f"Title: {criterion.title} | "
                    f"Description: {criterion.description}"
                )
        return context
    finally:
        if close_session:
            session.close()


def get_active_rubric_scoring_rules(
    agent_id: str, db: Any | None = None
) -> dict[str, str]:
    """Return ``{criterion_code: scoring_rule}`` for the active rubric set."""
    session = db or get_session_factory()()
    close_session = db is None
    try:
        rubric_set = _get_active_rubric_set(session, agent_id)
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
            c.criterion_code: c.scoring_rule
            for c in criteria
            if c.scoring_rule and c.scoring_rule.strip()
        }
    finally:
        if close_session:
            session.close()


__all__ = [
    "_get_active_rubric_set",
    "get_active_rubric_context",
    "get_active_rubric_scoring_rules",
]
