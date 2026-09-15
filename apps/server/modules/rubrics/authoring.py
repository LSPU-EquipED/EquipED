"""Rubric interactive editor mutations: domain and criterion CRUD and reordering."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func

from .contracts import StrategyConfig
from .exceptions import (
    RubricConflictError,
    RubricNotFoundError,
    RubricValidationError,
)
from .models import RubricCriterion, RubricDomain
from .revisions import _lock_parent_draft_rubric_set, get_revision_by_id
from .schemas import DomainReorderItem

_UNSET: Any = object()


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
    "create_criterion",
    "create_domain",
    "delete_criterion",
    "delete_domain",
    "move_criterion",
    "reorder_rubric_tree",
    "update_criterion",
    "update_domain",
]
