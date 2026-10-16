"""Explicit, offline-only Coordinator rubric authoring reset service."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from dataclasses import dataclass

from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import (
    EvaluationFormSnapshot,
    EvaluationRubricProvenance,
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)

COORDINATOR_AGENT_ID = "coordinator"
RESET_CONFIRMATION = "RESET_COORDINATOR_RUBRIC"
FRESH_V1_DRAFT_CONFIRMATION = "CREATE_COORDINATOR_RUBRIC_V1_DRAFT"
_IN_FLIGHT_STATUSES = (
    EvaluationStatus.SUBMITTED.value,
    EvaluationStatus.PREPROCESSING.value,
    EvaluationStatus.EVALUATING.value,
    EvaluationStatus.SYNTHESIZING.value,
)


@dataclass(frozen=True)
class CoordinatorRubricResetReport:
    """Counts and IDs captured before and after the authoring reset."""

    coordinator_rubric_set_ids: tuple[uuid.UUID, ...]
    coordinator_domain_count: int
    coordinator_criterion_count: int
    coordinator_activation_count: int
    snapshot_count_before: int
    provenance_count_before: int
    other_agent_rubric_set_count_after: int
    fresh_draft_id: uuid.UUID | None = None


def _count(session: Session, model: type, *criteria) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(model).where(*criteria)
        ).scalar_one()
    )


def _reset_in_transaction(
    session: Session,
    *,
    create_fresh_v1_draft: bool,
    expected_rubric_set_count: int | None,
    expected_snapshot_count: int | None,
    expected_provenance_count: int | None,
) -> CoordinatorRubricResetReport:
    """Perform the narrowly scoped reset inside the caller's transaction."""
    coordinator_sets = list(
        session.scalars(
            select(RubricSet)
            .where(RubricSet.agent_id == COORDINATOR_AGENT_ID)
            .order_by(RubricSet.rubric_set_id)
            .with_for_update()
        )
    )
    coordinator_set_ids = tuple(
        rubric_set.rubric_set_id for rubric_set in coordinator_sets
    )

    # Lock the relevant job rows before checking them so a queued or running
    # Coordinator evaluation cannot race this authoring reset.
    in_flight_jobs = list(
        session.scalars(
            select(EvaluationJob.evaluation_id)
            .where(
                EvaluationJob.target_agent.in_((COORDINATOR_AGENT_ID, "all")),
                EvaluationJob.status.in_(_IN_FLIGHT_STATUSES),
            )
            .with_for_update()
        )
    )
    if in_flight_jobs:
        raise RuntimeError(
            "Coordinator rubric reset stopped: in-flight Coordinator "
            "evaluation jobs exist"
        )

    snapshot_ids = set(
        session.scalars(select(EvaluationFormSnapshot.rubric_set_id).distinct())
    )
    provenance_ids = set(
        session.scalars(select(EvaluationRubricProvenance.rubric_set_id))
    )
    missing_provenance = snapshot_ids - provenance_ids
    if missing_provenance:
        raise RuntimeError(
            "Coordinator rubric reset stopped: snapshot provenance is incomplete"
        )

    snapshot_count = _count(session, EvaluationFormSnapshot)
    provenance_count = _count(session, EvaluationRubricProvenance)
    domain_count = _count(
        session,
        RubricDomain,
        RubricDomain.rubric_set_id.in_(coordinator_set_ids),
    )
    criterion_count = _count(
        session,
        RubricCriterion,
        RubricCriterion.rubric_domain_id.in_(
            select(RubricDomain.rubric_domain_id).where(
                RubricDomain.rubric_set_id.in_(coordinator_set_ids)
            )
        ),
    )
    activation_count = _count(
        session,
        RubricAgentActivation,
        RubricAgentActivation.agent_id == COORDINATOR_AGENT_ID,
    )

    expectations = (
        ("Coordinator rubric set", expected_rubric_set_count, len(coordinator_sets)),
        ("snapshot", expected_snapshot_count, snapshot_count),
        ("provenance", expected_provenance_count, provenance_count),
    )
    for label, expected, actual in expectations:
        if expected is not None and expected != actual:
            raise RuntimeError(
                f"Coordinator rubric reset stopped: expected {expected} {label} rows, "
                f"found {actual}"
            )

    session.execute(
        delete(RubricAgentActivation).where(
            RubricAgentActivation.agent_id == COORDINATOR_AGENT_ID
        )
    )
    session.execute(
        delete(RubricCriterion).where(
            RubricCriterion.rubric_domain_id.in_(
                select(RubricDomain.rubric_domain_id).where(
                    RubricDomain.rubric_set_id.in_(coordinator_set_ids)
                )
            )
        )
    )
    session.execute(
        delete(RubricDomain).where(RubricDomain.rubric_set_id.in_(coordinator_set_ids))
    )
    session.execute(delete(RubricSet).where(RubricSet.agent_id == COORDINATOR_AGENT_ID))

    fresh_draft_id: uuid.UUID | None = None
    if create_fresh_v1_draft:
        fresh_draft_id = uuid.uuid4()
        session.add(
            RubricSet(
                rubric_set_id=fresh_draft_id,
                agent_id=COORDINATOR_AGENT_ID,
                name="Coordinator Rubric v1",
                version_number=1,
                status="draft",
                adapter_key=COORDINATOR_AGENT_ID,
                adapter_version=3,
            )
        )

    session.flush()
    remaining_other_sets = _count(
        session,
        RubricSet,
        RubricSet.agent_id != COORDINATOR_AGENT_ID,
    )
    return CoordinatorRubricResetReport(
        coordinator_rubric_set_ids=coordinator_set_ids,
        coordinator_domain_count=domain_count,
        coordinator_criterion_count=criterion_count,
        coordinator_activation_count=activation_count,
        snapshot_count_before=snapshot_count,
        provenance_count_before=provenance_count,
        other_agent_rubric_set_count_after=remaining_other_sets,
        fresh_draft_id=fresh_draft_id,
    )


def reset_coordinator_rubric(
    session: Session,
    *,
    agent_id: str = COORDINATOR_AGENT_ID,
    confirmation: str | None = None,
    create_fresh_v1_draft: bool = False,
    fresh_draft_confirmation: str | None = None,
    expected_rubric_set_count: int | None = None,
    expected_snapshot_count: int | None = None,
    expected_provenance_count: int | None = None,
) -> CoordinatorRubricResetReport:
    """Delete only Coordinator authoring rows after explicit confirmation.

    The service never deletes snapshots or provenance and never publishes or
    activates a replacement. Optional expected counts provide a pre-delete
    backup/safety check. Callers with an existing transaction retain ownership
    of commit/rollback; a standalone call gets its own transaction.
    """
    if agent_id != COORDINATOR_AGENT_ID:
        raise ValueError("This reset service only accepts agent_id='coordinator'")
    if confirmation != RESET_CONFIRMATION:
        raise ValueError(
            f"Coordinator rubric reset requires confirmation={RESET_CONFIRMATION!r}"
        )
    if (
        create_fresh_v1_draft
        and fresh_draft_confirmation != FRESH_V1_DRAFT_CONFIRMATION
    ):
        raise ValueError(
            "Creating a fresh v1 draft requires separate confirmation="
            f"{FRESH_V1_DRAFT_CONFIRMATION!r}"
        )
    if not create_fresh_v1_draft and fresh_draft_confirmation is not None:
        raise ValueError("Fresh-draft confirmation requires create_fresh_v1_draft=True")
    for label, expected in (
        ("expected_rubric_set_count", expected_rubric_set_count),
        ("expected_snapshot_count", expected_snapshot_count),
        ("expected_provenance_count", expected_provenance_count),
    ):
        if expected is not None and expected < 0:
            raise ValueError(f"{label} must be non-negative")

    transaction = nullcontext() if session.in_transaction() else session.begin()
    with transaction:
        return _reset_in_transaction(
            session,
            create_fresh_v1_draft=create_fresh_v1_draft,
            expected_rubric_set_count=expected_rubric_set_count,
            expected_snapshot_count=expected_snapshot_count,
            expected_provenance_count=expected_provenance_count,
        )


__all__ = [
    "COORDINATOR_AGENT_ID",
    "FRESH_V1_DRAFT_CONFIRMATION",
    "RESET_CONFIRMATION",
    "CoordinatorRubricResetReport",
    "reset_coordinator_rubric",
]
