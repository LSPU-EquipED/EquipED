"""Rubric revision lifecycle management: drafts, validation, publishing, activation."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from server.core.database import get_session_factory

from .contracts import ValidationReport
from .exceptions import (
    RubricConflictError,
    RubricNotFoundError,
    RubricValidationError,
)
from .models import RubricAgentActivation, RubricCriterion, RubricDomain, RubricSet
from .repository import (
    activate_revision,
    create_draft_from_active,
    delete_draft_revision,
    lock_draft_rubric_set,
    orm_to_form_definition,
    publish_draft_revision,
    retire_revision,
    validate_form_definition,
)


def _format_rubric_set(
    rubric_set: RubricSet,
    domains: Sequence[RubricDomain],
    criteria: Sequence[RubricCriterion],
    *,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """Format an ORM RubricSet and its child rows into a clean dictionary."""
    criteria_by_domain: dict[uuid.UUID, list[RubricCriterion]] = {}
    for crit in criteria:
        criteria_by_domain.setdefault(crit.rubric_domain_id, []).append(crit)

    sorted_domains = sorted(domains, key=lambda d: (d.display_order, d.code))

    return {
        "rubric_set_id": rubric_set.rubric_set_id,
        "agent_id": rubric_set.agent_id,
        "name": rubric_set.name,
        "version_number": rubric_set.version_number,
        "status": rubric_set.status,
        "adapter_key": rubric_set.adapter_key,
        "adapter_version": rubric_set.adapter_version,
        "published_at": rubric_set.published_at,
        "published_by": rubric_set.published_by,
        "created_at": rubric_set.created_at,
        "created_by": rubric_set.created_by,
        "retired_at": rubric_set.retired_at,
        "retired_by": rubric_set.retired_by,
        "is_active": is_active,
        "domains": [
            {
                "rubric_domain_id": domain.rubric_domain_id,
                "rubric_set_id": domain.rubric_set_id,
                "code": domain.code,
                "title": domain.title,
                "display_order": domain.display_order,
                "criteria": [
                    {
                        "rubric_criterion_id": c.rubric_criterion_id,
                        "rubric_domain_id": c.rubric_domain_id,
                        "criterion_code": c.criterion_code,
                        "title": c.title,
                        "description": c.description,
                        "scoring_rule": c.scoring_rule,
                        "scoring_strategy": c.scoring_strategy,
                        "strategy_config": c.strategy_config,
                        "display_order": c.display_order,
                    }
                    for c in sorted(
                        criteria_by_domain.get(domain.rubric_domain_id, []),
                        key=lambda c: (c.display_order, c.criterion_code),
                    )
                ],
            }
            for domain in sorted_domains
        ],
    }


def get_rubric_sets_for_editor(db: Any | None = None) -> list[dict[str, Any]]:
    """Return every active published rubric set, fully nested, for the admin editor."""
    session = db or get_session_factory()()
    close_session = db is None
    try:
        activations = session.query(RubricAgentActivation).all()
        if not activations:
            return []

        activation_map = {a.rubric_set_id: a.agent_id for a in activations}
        candidate_sets = (
            session.query(RubricSet)
            .filter(
                RubricSet.rubric_set_id.in_(list(activation_map.keys())),
                RubricSet.status == "published",
            )
            .all()
        )
        valid_sets = [
            s
            for s in candidate_sets
            if s.agent_id == activation_map.get(s.rubric_set_id)
        ]

        sets_by_agent: dict[str, RubricSet] = {}
        for rubric_set in valid_sets:
            sets_by_agent.setdefault(rubric_set.agent_id, rubric_set)

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
        criteria_by_set: dict[uuid.UUID, list[RubricCriterion]] = {}
        domain_to_set = {d.rubric_domain_id: d.rubric_set_id for d in domains}
        for criterion in criteria:
            parent_set = domain_to_set.get(criterion.rubric_domain_id)
            if parent_set:
                criteria_by_set.setdefault(parent_set, []).append(criterion)

        return [
            _format_rubric_set(
                s,
                domains_by_set.get(s.rubric_set_id, []),
                criteria_by_set.get(s.rubric_set_id, []),
                is_active=True,
            )
            for s in active_sets
        ]
    finally:
        if close_session:
            session.close()


def get_all_revisions(db: Any, *, agent_id: str | None = None) -> dict[str, Any]:
    """Return all rubric revisions with active pointer metadata."""
    query = db.query(RubricSet)
    if agent_id:
        query = query.filter(RubricSet.agent_id == agent_id)

    agent_order = {"sme": 0, "coordinator": 1, "gad": 2, "itso": 3}
    all_sets = query.all()
    sorted_sets = sorted(
        all_sets,
        key=lambda s: (
            agent_order.get(s.agent_id, 99),
            s.agent_id,
            -s.version_number,
        ),
    )

    activations = db.query(RubricAgentActivation).all()
    active_pointers = {a.agent_id: a.rubric_set_id for a in activations}
    active_set_ids = set(active_pointers.values())

    set_ids = [s.rubric_set_id for s in sorted_sets]
    if not set_ids:
        return {"revisions": [], "active_pointers": active_pointers}

    domains = (
        db.query(RubricDomain)
        .filter(RubricDomain.rubric_set_id.in_(set_ids))
        .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
        .all()
    )
    domains_by_set: dict[uuid.UUID, list[RubricDomain]] = {}
    for domain in domains:
        domains_by_set.setdefault(domain.rubric_set_id, []).append(domain)

    domain_ids = [d.rubric_domain_id for d in domains]
    criteria = (
        db.query(RubricCriterion)
        .filter(RubricCriterion.rubric_domain_id.in_(domain_ids))
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
        )
        .all()
    )
    criteria_by_set: dict[uuid.UUID, list[RubricCriterion]] = {}
    domain_to_set = {d.rubric_domain_id: d.rubric_set_id for d in domains}
    for criterion in criteria:
        parent_set = domain_to_set.get(criterion.rubric_domain_id)
        if parent_set:
            criteria_by_set.setdefault(parent_set, []).append(criterion)

    revisions = [
        _format_rubric_set(
            s,
            domains_by_set.get(s.rubric_set_id, []),
            criteria_by_set.get(s.rubric_set_id, []),
            is_active=(s.rubric_set_id in active_set_ids),
        )
        for s in sorted_sets
    ]
    return {"revisions": revisions, "active_pointers": active_pointers}


def get_revision_by_id(db: Any, rubric_set_id: uuid.UUID) -> dict[str, Any]:
    """Load a specific revision by rubric_set_id fully nested."""
    rubric_set = (
        db.query(RubricSet).filter_by(rubric_set_id=rubric_set_id).one_or_none()
    )
    if rubric_set is None:
        raise RubricNotFoundError(f"Rubric set {rubric_set_id} not found")

    domains = (
        db.query(RubricDomain)
        .filter_by(rubric_set_id=rubric_set.rubric_set_id)
        .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
        .all()
    )
    criteria = (
        db.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
        )
        .all()
    )

    activation = (
        db.query(RubricAgentActivation)
        .filter_by(agent_id=rubric_set.agent_id)
        .one_or_none()
    )
    is_active = (
        activation is not None and activation.rubric_set_id == rubric_set.rubric_set_id
    )

    return _format_rubric_set(rubric_set, domains, criteria, is_active=is_active)


def _lock_parent_draft_rubric_set(db: Any, rubric_set_id: uuid.UUID) -> RubricSet:
    """Shared parent-lock helper ensuring target rubric set is draft and locked."""
    try:
        return lock_draft_rubric_set(db, rubric_set_id)
    except ValueError as exc:
        raise RubricConflictError(str(exc)) from exc
    except LookupError as exc:
        raise RubricNotFoundError(str(exc)) from exc


def create_draft_for_agent(
    db: Any, agent_id: str, *, actor_id: uuid.UUID
) -> dict[str, Any]:
    """Clone the active published revision into a single editable draft for an agent."""
    try:
        draft = create_draft_from_active(db, agent_id, actor_id=actor_id)
    except LookupError as exc:
        raise RubricNotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise RubricConflictError(str(exc)) from exc

    return get_revision_by_id(db, draft.rubric_set_id)


def delete_draft(db: Any, rubric_set_id: uuid.UUID) -> None:
    """Delete a draft revision and its child domains/criteria."""
    try:
        delete_draft_revision(db, rubric_set_id)
    except LookupError as exc:
        raise RubricNotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise RubricConflictError(str(exc)) from exc


def validate_draft_revision(db: Any, rubric_set_id: uuid.UUID) -> ValidationReport:
    """Validate a draft or revision against its capability manifest."""
    rubric_set = (
        db.query(RubricSet).filter_by(rubric_set_id=rubric_set_id).one_or_none()
    )
    if rubric_set is None:
        raise RubricNotFoundError(f"Rubric set {rubric_set_id} not found")

    domains = (
        db.query(RubricDomain)
        .filter_by(rubric_set_id=rubric_set.rubric_set_id)
        .order_by(RubricDomain.display_order.asc(), RubricDomain.code.asc())
        .all()
    )
    criteria = (
        db.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == rubric_set.rubric_set_id)
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
        )
        .all()
    )

    try:
        form_def = orm_to_form_definition(rubric_set, domains, criteria)
    except ValueError as exc:
        raise RubricValidationError(str(exc)) from exc

    return validate_form_definition(form_def)


def publish_revision(
    db: Any,
    rubric_set_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    activate: bool = True,
) -> dict[str, Any]:
    """Publish a draft revision and optionally activate it atomically."""
    try:
        published_set, _ = publish_draft_revision(
            db, rubric_set_id, actor_id=actor_id, activate=activate
        )
    except RubricValidationError:
        raise
    except LookupError as exc:
        raise RubricNotFoundError(str(exc)) from exc
    except ValueError as exc:
        err_msg = str(exc)
        if (
            "Cannot publish non-draft" in err_msg
            or "Cannot activate: no existing activation" in err_msg
        ):
            raise RubricConflictError(err_msg) from exc
        raise RubricValidationError(err_msg) from exc

    return get_revision_by_id(db, published_set.rubric_set_id)


def activate_revision_by_id(
    db: Any, rubric_set_id: uuid.UUID, *, actor_id: uuid.UUID
) -> RubricAgentActivation:
    """Activate a published revision for its agent."""
    rubric_set = (
        db.query(RubricSet).filter_by(rubric_set_id=rubric_set_id).one_or_none()
    )
    if rubric_set is None:
        raise RubricNotFoundError(f"Rubric set {rubric_set_id} not found")

    try:
        activation = activate_revision(
            db, rubric_set.agent_id, rubric_set_id, actor_id=actor_id
        )
    except RubricValidationError:
        raise
    except LookupError as exc:
        raise RubricNotFoundError(str(exc)) from exc
    except ValueError as exc:
        err_msg = str(exc)
        if (
            "Cannot activate invalid revision" in err_msg
            or "failed capability manifest" in err_msg
        ):
            raise RubricValidationError(err_msg) from exc
        raise RubricConflictError(err_msg) from exc

    return activation


def retire_revision_by_id(
    db: Any, rubric_set_id: uuid.UUID, *, actor_id: uuid.UUID
) -> dict[str, Any]:
    """Retire a non-active published revision."""
    rubric_set = (
        db.query(RubricSet).filter_by(rubric_set_id=rubric_set_id).one_or_none()
    )
    if rubric_set is None:
        raise RubricNotFoundError(f"Rubric set {rubric_set_id} not found")

    try:
        retired = retire_revision(
            db, rubric_set.agent_id, rubric_set_id, actor_id=actor_id
        )
    except LookupError as exc:
        raise RubricNotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise RubricConflictError(str(exc)) from exc

    return get_revision_by_id(db, retired.rubric_set_id)


__all__ = [
    "_format_rubric_set",
    "_lock_parent_draft_rubric_set",
    "activate_revision_by_id",
    "create_draft_for_agent",
    "delete_draft",
    "get_all_revisions",
    "get_revision_by_id",
    "get_rubric_sets_for_editor",
    "publish_revision",
    "retire_revision_by_id",
    "validate_draft_revision",
]
