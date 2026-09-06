"""Rubric loading helpers and admin lifecycle facade for relational rubric storage."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from server.core.database import get_session_factory
from sqlalchemy import func

from .contracts import StrategyConfig, ValidationReport
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
from .schemas import DomainReorderItem

_UNSET: Any = object()


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


def create_domain(
    db: Any,
    rubric_set_id: uuid.UUID,
    *,
    code: str,
    title: str,
) -> RubricDomain:
    """Add a new domain to a draft rubric set (appends to end)."""
    _lock_parent_draft_rubric_set(db, rubric_set_id)

    code_clean = code.strip().upper()
    existing = (
        db.query(RubricDomain)
        .filter_by(rubric_set_id=rubric_set_id, code=code_clean)
        .first()
    )
    if existing is not None:
        raise RubricConflictError(
            f"Domain with code '{code_clean}' already exists in rubric "
            f"set {rubric_set_id}"
        )

    max_order = (
        db.query(func.max(RubricDomain.display_order))
        .filter_by(rubric_set_id=rubric_set_id)
        .scalar()
    )
    display_order = (max_order or 0) + 1

    domain = RubricDomain(
        rubric_domain_id=uuid.uuid4(),
        rubric_set_id=rubric_set_id,
        code=code_clean,
        title=title.strip(),
        display_order=display_order,
    )
    db.add(domain)
    db.flush()
    return domain


def update_domain(
    db: Any,
    domain_id: uuid.UUID,
    *,
    title: str | None = None,
    code: str | None = None,
) -> RubricDomain:
    """Update a domain's title or code in a draft rubric set."""
    row = (
        db.query(RubricDomain.rubric_domain_id, RubricDomain.rubric_set_id)
        .filter(RubricDomain.rubric_domain_id == domain_id)
        .one_or_none()
    )
    if row is None:
        raise RubricNotFoundError(f"Rubric domain {domain_id} not found")

    rubric_set_id = row[1]
    _lock_parent_draft_rubric_set(db, rubric_set_id)

    domain = (
        db.query(RubricDomain)
        .filter(
            RubricDomain.rubric_domain_id == domain_id,
            RubricDomain.rubric_set_id == rubric_set_id,
        )
        .one_or_none()
    )
    if domain is None:
        raise RubricNotFoundError(
            f"Rubric domain {domain_id} not found under rubric set {rubric_set_id}"
        )

    if code is not None:
        clean_code = code.strip().upper()
        if clean_code != domain.code:
            existing = (
                db.query(RubricDomain)
                .filter(
                    RubricDomain.rubric_set_id == rubric_set_id,
                    RubricDomain.code == clean_code,
                    RubricDomain.rubric_domain_id != domain_id,
                )
                .first()
            )
            if existing is not None:
                raise RubricConflictError(
                    f"Domain code '{clean_code}' already exists in rubric "
                    f"set {rubric_set_id}"
                )
            domain.code = clean_code

    if title is not None:
        domain.title = title.strip()

    db.flush()
    return domain


def delete_domain(db: Any, domain_id: uuid.UUID) -> None:
    """Delete a domain and its child criteria from a draft rubric set."""
    row = (
        db.query(RubricDomain.rubric_domain_id, RubricDomain.rubric_set_id)
        .filter(RubricDomain.rubric_domain_id == domain_id)
        .one_or_none()
    )
    if row is None:
        raise RubricNotFoundError(f"Rubric domain {domain_id} not found")

    rubric_set_id = row[1]
    _lock_parent_draft_rubric_set(db, rubric_set_id)

    db.query(RubricCriterion).filter_by(rubric_domain_id=domain_id).delete()
    db.query(RubricDomain).filter_by(rubric_domain_id=domain_id).delete()
    db.flush()


def create_criterion(
    db: Any,
    domain_id: uuid.UUID,
    *,
    criterion_code: str,
    title: str,
    description: str,
    scoring_rule: str | None,
    strategy_config: StrategyConfig,
) -> RubricCriterion:
    """Add a new criterion to a domain in a draft rubric set (appends to end)."""
    parent_row = (
        db.query(RubricDomain.rubric_set_id)
        .filter(RubricDomain.rubric_domain_id == domain_id)
        .one_or_none()
    )
    if parent_row is None:
        raise RubricNotFoundError(f"Rubric domain {domain_id} not found")

    rubric_set_id = parent_row[0]
    _lock_parent_draft_rubric_set(db, rubric_set_id)

    domain = (
        db.query(RubricDomain)
        .filter(
            RubricDomain.rubric_domain_id == domain_id,
            RubricDomain.rubric_set_id == rubric_set_id,
        )
        .one_or_none()
    )
    if domain is None:
        raise RubricNotFoundError(
            f"Rubric domain {domain_id} no longer exists under locked rubric set "
            f"{rubric_set_id}"
        )

    code_clean = criterion_code.strip()
    all_criteria = (
        db.query(RubricCriterion.criterion_code)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == rubric_set_id)
        .all()
    )
    for (existing_code,) in all_criteria:
        if existing_code.casefold() == code_clean.casefold():
            raise RubricConflictError(
                f"Criterion code '{code_clean}' already exists in rubric "
                f"set {rubric_set_id}"
            )

    scoring_strategy = strategy_config.strategy
    config_dict = strategy_config.model_dump(mode="json")

    max_order = (
        db.query(func.max(RubricCriterion.display_order))
        .filter_by(rubric_domain_id=domain_id)
        .scalar()
    )
    display_order = (max_order or 0) + 1

    clean_rule = scoring_rule.strip() if scoring_rule and scoring_rule.strip() else None

    criterion = RubricCriterion(
        rubric_criterion_id=uuid.uuid4(),
        rubric_domain_id=domain_id,
        criterion_code=code_clean,
        title=title.strip(),
        description=description.strip(),
        scoring_rule=clean_rule,
        scoring_strategy=scoring_strategy,
        strategy_config=config_dict,
        display_order=display_order,
    )
    db.add(criterion)
    db.flush()
    return criterion


def move_criterion(
    db: Any,
    criterion_id: uuid.UUID,
    *,
    destination_domain_id: uuid.UUID,
) -> RubricCriterion:
    """Move one criterion to another domain in the same locked draft."""
    source_row = (
        db.query(RubricDomain.rubric_set_id)
        .join(
            RubricCriterion,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricCriterion.rubric_criterion_id == criterion_id)
        .one_or_none()
    )
    if source_row is None:
        raise RubricNotFoundError(f"Rubric criterion {criterion_id} not found")

    destination_row = (
        db.query(RubricDomain.rubric_set_id)
        .filter(RubricDomain.rubric_domain_id == destination_domain_id)
        .one_or_none()
    )
    if destination_row is None:
        raise RubricNotFoundError(
            f"Destination rubric domain {destination_domain_id} not found"
        )

    rubric_set_id = source_row[0]
    if destination_row[0] != rubric_set_id:
        raise RubricConflictError(
            "Criterion and destination domain must belong to the same rubric draft"
        )

    _lock_parent_draft_rubric_set(db, rubric_set_id)

    criterion = (
        db.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(
            RubricCriterion.rubric_criterion_id == criterion_id,
            RubricDomain.rubric_set_id == rubric_set_id,
        )
        .one_or_none()
    )
    if criterion is None:
        raise RubricNotFoundError(
            f"Rubric criterion {criterion_id} no longer exists under locked "
            f"rubric set {rubric_set_id}"
        )

    destination = (
        db.query(RubricDomain)
        .filter(
            RubricDomain.rubric_domain_id == destination_domain_id,
            RubricDomain.rubric_set_id == rubric_set_id,
        )
        .one_or_none()
    )
    if destination is None:
        raise RubricConflictError(
            "Destination domain changed or disappeared while acquiring the draft lock"
        )

    source_domain_id = criterion.rubric_domain_id
    if source_domain_id == destination_domain_id:
        domain_criteria = (
            db.query(RubricCriterion)
            .filter(RubricCriterion.rubric_domain_id == source_domain_id)
            .order_by(
                RubricCriterion.display_order.asc(),
                RubricCriterion.criterion_code.asc(),
                RubricCriterion.rubric_criterion_id.asc(),
            )
            .all()
        )
        for index, domain_criterion in enumerate(domain_criteria, start=1):
            domain_criterion.display_order = index
        db.flush()
        return criterion

    source_criteria = (
        db.query(RubricCriterion)
        .filter(
            RubricCriterion.rubric_domain_id == source_domain_id,
            RubricCriterion.rubric_criterion_id != criterion_id,
        )
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
            RubricCriterion.rubric_criterion_id.asc(),
        )
        .all()
    )
    destination_criteria = (
        db.query(RubricCriterion)
        .filter(
            RubricCriterion.rubric_domain_id == destination_domain_id,
            RubricCriterion.rubric_criterion_id != criterion_id,
        )
        .order_by(
            RubricCriterion.display_order.asc(),
            RubricCriterion.criterion_code.asc(),
            RubricCriterion.rubric_criterion_id.asc(),
        )
        .all()
    )

    for index, source_criterion in enumerate(source_criteria, start=1):
        source_criterion.display_order = index
    for index, destination_criterion in enumerate(destination_criteria, start=1):
        destination_criterion.display_order = index

    criterion.rubric_domain_id = destination_domain_id
    criterion.display_order = len(destination_criteria) + 1
    db.flush()
    return criterion


def update_criterion(
    db: Any,
    criterion_id: uuid.UUID,
    *,
    description: str | None = None,
    scoring_rule: Any = _UNSET,
    title: str | None = None,
    criterion_code: str | None = None,
    strategy_config: StrategyConfig | None = None,
) -> RubricCriterion:
    """Update a criterion in a draft rubric set."""
    row = (
        db.query(RubricCriterion.rubric_criterion_id, RubricDomain.rubric_set_id)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricCriterion.rubric_criterion_id == criterion_id)
        .one_or_none()
    )
    if row is None:
        raise RubricNotFoundError(f"Rubric criterion {criterion_id} not found")

    rubric_set_id = row[1]
    _lock_parent_draft_rubric_set(db, rubric_set_id)

    criterion = (
        db.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(
            RubricCriterion.rubric_criterion_id == criterion_id,
            RubricDomain.rubric_set_id == rubric_set_id,
        )
        .one_or_none()
    )
    if criterion is None:
        raise RubricNotFoundError(
            f"Rubric criterion {criterion_id} not found "
            f"under rubric set {rubric_set_id}"
        )

    if criterion_code is not None:
        clean_code = criterion_code.strip()
        if clean_code.casefold() != criterion.criterion_code.casefold():
            other_criteria = (
                db.query(RubricCriterion.criterion_code)
                .join(
                    RubricDomain,
                    RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
                )
                .filter(
                    RubricDomain.rubric_set_id == rubric_set_id,
                    RubricCriterion.rubric_criterion_id != criterion_id,
                )
                .all()
            )
            for (existing_code,) in other_criteria:
                if existing_code.casefold() == clean_code.casefold():
                    raise RubricConflictError(
                        f"Criterion code '{clean_code}' already exists in rubric "
                        f"set {rubric_set_id}"
                    )
            criterion.criterion_code = clean_code

    if title is not None:
        criterion.title = title.strip()

    if description is not None:
        criterion.description = description.strip()

    if scoring_rule is not _UNSET:
        if scoring_rule is None:
            criterion.scoring_rule = None
        elif isinstance(scoring_rule, str):
            stripped = scoring_rule.strip()
            criterion.scoring_rule = stripped if stripped else None

    if strategy_config is not None:
        criterion.scoring_strategy = strategy_config.strategy
        criterion.strategy_config = strategy_config.model_dump(mode="json")

    db.flush()
    return criterion


def delete_criterion(db: Any, criterion_id: uuid.UUID) -> None:
    """Delete a criterion from a draft rubric set."""
    row = (
        db.query(RubricCriterion.rubric_criterion_id, RubricDomain.rubric_set_id)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricCriterion.rubric_criterion_id == criterion_id)
        .one_or_none()
    )
    if row is None:
        raise RubricNotFoundError(f"Rubric criterion {criterion_id} not found")

    rubric_set_id = row[1]
    _lock_parent_draft_rubric_set(db, rubric_set_id)

    db.query(RubricCriterion).filter_by(rubric_criterion_id=criterion_id).delete()
    db.flush()


def reorder_rubric_tree(
    db: Any,
    rubric_set_id: uuid.UUID,
    domain_orders: Sequence[DomainReorderItem],
) -> dict[str, Any]:
    """Atomic, ordering-only bulk reorder of domains and criteria within a draft.

    Enforces:
    - Target rubric set is draft (locked exclusively).
    - Every existing domain in draft is submitted exactly once.
    - Every existing criterion in each domain is submitted under its CURRENT domain.
    - If any check fails, raises RubricValidationError with zero partial writes.
    - Updates display_order values sequentially.
    """
    _lock_parent_draft_rubric_set(db, rubric_set_id)

    domains = db.query(RubricDomain).filter_by(rubric_set_id=rubric_set_id).all()
    existing_domains = {d.rubric_domain_id: d for d in domains}

    criteria = (
        db.query(RubricCriterion)
        .join(
            RubricDomain,
            RubricCriterion.rubric_domain_id == RubricDomain.rubric_domain_id,
        )
        .filter(RubricDomain.rubric_set_id == rubric_set_id)
        .all()
    )
    existing_criteria = {c.rubric_criterion_id: c for c in criteria}
    domain_to_criteria: dict[uuid.UUID, set[uuid.UUID]] = {
        d.rubric_domain_id: set() for d in domains
    }
    for c in criteria:
        domain_to_criteria[c.rubric_domain_id].add(c.rubric_criterion_id)

    submitted_domain_ids = [item.rubric_domain_id for item in domain_orders]
    if len(submitted_domain_ids) != len(set(submitted_domain_ids)):
        raise RubricValidationError("Duplicate domain IDs in reorder request")

    if set(submitted_domain_ids) != set(existing_domains.keys()):
        raise RubricValidationError(
            "Reorder request must include all existing domains for this draft "
            "without omissions or foreign domain IDs"
        )

    all_submitted_criterion_ids: list[uuid.UUID] = []
    for item in domain_orders:
        dom_id = item.rubric_domain_id
        dom_crit_ids = item.criterion_ids
        if len(dom_crit_ids) != len(set(dom_crit_ids)):
            raise RubricValidationError(f"Duplicate criterion IDs in domain '{dom_id}'")

        expected_crit_ids = domain_to_criteria[dom_id]
        if set(dom_crit_ids) != expected_crit_ids:
            raise RubricValidationError(
                f"Reorder criteria for domain '{dom_id}' must exactly match existing "
                "criteria in that domain (reparenting across domains, foreign IDs, "
                "or omissions are forbidden)"
            )
        all_submitted_criterion_ids.extend(dom_crit_ids)

    if len(all_submitted_criterion_ids) != len(set(all_submitted_criterion_ids)):
        raise RubricValidationError(
            "Duplicate criterion IDs across domains in reorder request"
        )

    # All validations passed: apply new display_order values atomically
    for d_idx, item in enumerate(domain_orders):
        domain = existing_domains[item.rubric_domain_id]
        domain.display_order = d_idx + 1
        for c_idx, crit_id in enumerate(item.criterion_ids):
            crit = existing_criteria[crit_id]
            crit.display_order = c_idx + 1

    db.flush()
    return get_revision_by_id(db, rubric_set_id)


__all__ = [
    "_UNSET",
    "activate_revision_by_id",
    "create_criterion",
    "create_domain",
    "create_draft_for_agent",
    "delete_criterion",
    "delete_domain",
    "delete_draft",
    "get_active_rubric_context",
    "get_active_rubric_scoring_rules",
    "get_all_revisions",
    "get_revision_by_id",
    "get_rubric_sets_for_editor",
    "move_criterion",
    "publish_revision",
    "reorder_rubric_tree",
    "retire_revision_by_id",
    "update_criterion",
    "update_domain",
    "validate_draft_revision",
]
