"""Rubric loading helpers for relational rubric storage."""

from __future__ import annotations

import uuid
from typing import Any

from server.core.database import get_session_factory

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


def get_active_rubric_scoring_rules(
    agent_id: str, db: Any | None = None
) -> dict[str, str]:
    """Return ``{criterion_code: scoring_rule}`` for the active rubric set.

    Mirrors ``get_active_rubric_descriptions`` but returns the per-criterion
    scoring rule (the "count X, band 1-4" text). Criteria whose
    ``scoring_rule`` is NULL or blank are omitted. Returns ``{}`` if no
    active rubric set exists.
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
            c.criterion_code: c.scoring_rule
            for c in criteria
            if c.scoring_rule and c.scoring_rule.strip()
        }
    finally:
        if close_session:
            session.close()


def get_rubric_sets_for_editor(db: Any | None = None) -> list[dict[str, Any]]:
    """Return every active rubric set, fully nested, for the admin editor.

    Shape matches ``RubricSetOut``: one dict per agent with ``domains`` ->
    ``criteria``. Uses three queries total (sets, domains, criteria) regardless
    of how many domains exist, to avoid N+1.
    """

    session = db or get_session_factory()()
    close_session = db is None
    try:
        rubric_sets = (
            session.query(RubricSet)
            .filter_by(status="active")
            .order_by(RubricSet.agent_id.asc(), RubricSet.version_number.desc())
            .all()
        )
        # One active set per agent; keep the highest version if duplicates exist.
        sets_by_agent: dict[str, RubricSet] = {}
        for rubric_set in rubric_sets:
            sets_by_agent.setdefault(rubric_set.agent_id, rubric_set)
        # Present agents in evaluation order, not alphabetically.
        agent_order = {"sme": 0, "coordinator": 1, "gad": 2, "itso": 3}
        active_sets = sorted(
            sets_by_agent.values(),
            key=lambda s: (agent_order.get(s.agent_id, len(agent_order)), s.agent_id),
        )
        set_ids = [s.rubric_set_id for s in active_sets]
        if not set_ids:
            return []

        domains = (
            session.query(RubricDomain)
            .filter(RubricDomain.rubric_set_id.in_(set_ids))
            .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
            .all()
        )
        domains_by_set: dict[uuid.UUID, list[RubricDomain]] = {}
        for domain in domains:
            domains_by_set.setdefault(domain.rubric_set_id, []).append(domain)

        criteria = (
            session.query(RubricCriterion)
            .filter(
                RubricCriterion.rubric_domain_id.in_(
                    [d.rubric_domain_id for d in domains]
                )
            )
            .order_by(
                RubricCriterion.display_order.asc(),
                RubricCriterion.criterion_code.asc(),
            )
            .all()
        )
        criteria_by_domain: dict[uuid.UUID, list[RubricCriterion]] = {}
        for criterion in criteria:
            criteria_by_domain.setdefault(criterion.rubric_domain_id, []).append(
                criterion
            )

        return [
            {
                "rubric_set_id": rubric_set.rubric_set_id,
                "agent_id": rubric_set.agent_id,
                "name": rubric_set.name,
                "version_number": rubric_set.version_number,
                "status": rubric_set.status,
                "domains": [
                    {
                        "rubric_domain_id": domain.rubric_domain_id,
                        "code": domain.code,
                        "title": domain.title,
                        "display_order": domain.display_order,
                        "criteria": [
                            {
                                "rubric_criterion_id": c.rubric_criterion_id,
                                "criterion_code": c.criterion_code,
                                "title": c.title,
                                "description": c.description,
                                "scoring_rule": c.scoring_rule,
                                "display_order": c.display_order,
                            }
                            for c in criteria_by_domain.get(
                                domain.rubric_domain_id, []
                            )
                        ],
                    }
                    for domain in domains_by_set.get(rubric_set.rubric_set_id, [])
                ],
            }
            for rubric_set in active_sets
        ]
    finally:
        if close_session:
            session.close()


def update_criterion(
    db: Any,
    criterion_id: uuid.UUID,
    *,
    description: str,
    scoring_rule: str | None,
) -> RubricCriterion:
    """Update a criterion's description and scoring rule in place.

    ``criterion_code`` and ``title`` are never changed here. A blank or
    ``None`` ``scoring_rule`` is stored as SQL NULL. Raises ``LookupError``
    when the id does not exist so the router can map it to a 404.
    """

    criterion = (
        db.query(RubricCriterion)
        .filter_by(rubric_criterion_id=criterion_id)
        .one_or_none()
    )
    if criterion is None:
        raise LookupError(f"rubric criterion {criterion_id} not found")
    criterion.description = description
    criterion.scoring_rule = (
        scoring_rule.strip() if scoring_rule and scoring_rule.strip() else None
    )
    db.flush()
    return criterion


def update_domain_title(db: Any, domain_id: uuid.UUID, *, title: str) -> RubricDomain:
    """Update a domain's title in place. Raises ``LookupError`` when missing."""

    domain = (
        db.query(RubricDomain).filter_by(rubric_domain_id=domain_id).one_or_none()
    )
    if domain is None:
        raise LookupError(f"rubric domain {domain_id} not found")
    domain.title = title
    db.flush()
    return domain


__all__ = [
    "get_active_rubric_context",
    "get_active_rubric_criteria",
    "get_active_rubric_descriptions",
    "get_active_rubric_scoring_rules",
    "get_rubric_sets_for_editor",
    "resolve_rubric_agent_id",
    "update_criterion",
    "update_domain_title",
]
