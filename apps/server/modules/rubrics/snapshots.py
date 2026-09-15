"""Evaluation form snapshot persistence, resolution, and verification service."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .contracts import MAX_CODE_LENGTH, FormDefinition
from .manifests import get_agent_manifest
from .models import EvaluationFormSnapshot
from .repository import load_active_form_definitions, validate_form_definition
from .snapshot_contracts import (
    EvaluationFormSnapshotDTO,
    SnapshotIntegrityError,
    build_evaluation_form_snapshot,
    verify_evaluation_form_snapshot,
)


def _normalize_and_validate_scheduled_agents(
    scheduled_agent_ids: Sequence[str],
) -> tuple[str, ...]:
    """Validate scheduled_agent_ids is a non-empty, duplicate-free sequence."""
    if (
        scheduled_agent_ids is None
        or isinstance(scheduled_agent_ids, (str, bytes))
        or not isinstance(scheduled_agent_ids, Sequence)
    ):
        raise SnapshotIntegrityError(
            "scheduled_agent_ids must be a non-string sequence"
        )

    agent_tuple = tuple(scheduled_agent_ids)
    if not agent_tuple:
        raise SnapshotIntegrityError("scheduled_agent_ids cannot be empty")

    seen_agents: set[str] = set()
    for agent_id in agent_tuple:
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise SnapshotIntegrityError(
                "scheduled_agent_ids contains invalid empty agent ID"
            )
        if len(agent_id) > MAX_CODE_LENGTH:
            raise SnapshotIntegrityError(
                "scheduled_agent_ids contains agent ID exceeding maximum code length"
            )
        if agent_id in seen_agents:
            raise SnapshotIntegrityError("Duplicate agent ID in scheduled_agent_ids")
        seen_agents.add(agent_id)
        try:
            get_agent_manifest(agent_id)
        except ValueError as exc:
            raise SnapshotIntegrityError("Unknown scheduled agent ID") from exc

    return agent_tuple


def _verify_and_validate_row(row: EvaluationFormSnapshot) -> EvaluationFormSnapshotDTO:
    """Verify single snapshot row integrity and revalidate form against budget."""
    try:
        dto = verify_evaluation_form_snapshot(
            snapshot_id=row.snapshot_id,
            evaluation_id=row.evaluation_id,
            agent_id=row.agent_id,
            rubric_set_id=row.rubric_set_id,
            adapter_key=row.adapter_key,
            adapter_version=row.adapter_version,
            snapshot_hash=row.snapshot_hash,
            snapshot_payload=row.snapshot_payload,
        )
    except (ValidationError, ValueError) as exc:
        raise SnapshotIntegrityError(
            "Evaluation form snapshot row failed pure integrity verification"
        ) from exc

    try:
        report = validate_form_definition(dto.form)
    except (ValidationError, ValueError) as exc:
        raise SnapshotIntegrityError(
            "Snapshot form definition validation failed against manifest/budget"
        ) from exc

    if not report.is_valid:
        raise SnapshotIntegrityError(
            "Snapshot form definition failed deployed budget validation"
        )
    return dto


def _verify_snapshot_row_set(
    rows: Sequence[EvaluationFormSnapshot],
    agents_tuple: tuple[str, ...],
    evaluation_id: uuid.UUID,
) -> tuple[EvaluationFormSnapshotDTO, ...]:
    """Verify exact scheduled row set and return verified DTO tuple in order."""
    found_agents = {r.agent_id for r in rows}
    expected_agents = set(agents_tuple)

    if len(rows) != len(agents_tuple) or found_agents != expected_agents:
        raise SnapshotIntegrityError(
            "Evaluation form snapshot set mismatch against scheduled agents"
        )

    verified_by_agent: dict[str, EvaluationFormSnapshotDTO] = {}
    for row in rows:
        dto = _verify_and_validate_row(row)
        verified_by_agent[row.agent_id] = dto

    return tuple(verified_by_agent[agent_id] for agent_id in agents_tuple)


def load_verified_evaluation_snapshots(
    session: Session,
    evaluation_id: uuid.UUID,
    scheduled_agent_ids: Sequence[str],
) -> tuple[EvaluationFormSnapshotDTO, ...]:
    """Load and verify evaluation form snapshots for scheduled agents in order.

    Fails with SnapshotIntegrityError on missing, partial, extra, or tampered snapshots.
    """
    if not isinstance(evaluation_id, uuid.UUID):
        raise SnapshotIntegrityError("evaluation_id must be a valid UUID")

    agents_tuple = _normalize_and_validate_scheduled_agents(scheduled_agent_ids)

    rows = (
        session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=evaluation_id)
        .all()
    )

    return _verify_snapshot_row_set(rows, agents_tuple, evaluation_id)


def persist_evaluation_form_snapshots(
    session: Session,
    evaluation_id: uuid.UUID,
    forms: Sequence[FormDefinition] | Mapping[str, FormDefinition],
) -> tuple[EvaluationFormSnapshotDTO, ...]:
    """Persist standard form snapshots from supplied exact FormDefinitions.

    Uses candidate building, deterministic canonical hashing, deployed budget
    validation, conflict-safe dialect insert, flush, and readback verification.
    Does NOT commit.
    """
    if not isinstance(evaluation_id, uuid.UUID):
        raise SnapshotIntegrityError("evaluation_id must be a valid UUID")

    if forms is None:
        raise SnapshotIntegrityError("forms must not be None")

    if isinstance(forms, Mapping):
        form_list = list(forms.values())
    elif isinstance(forms, Sequence) and not isinstance(forms, (str, bytes)):
        form_list = list(forms)
    else:
        raise SnapshotIntegrityError(
            "forms must be a sequence or mapping of FormDefinition"
        )

    if not form_list:
        raise SnapshotIntegrityError("forms cannot be empty")

    for f in form_list:
        if not isinstance(f, FormDefinition):
            raise SnapshotIntegrityError(
                "All items in forms must be FormDefinition instances"
            )

    agents_tuple = _normalize_and_validate_scheduled_agents(
        [f.agent_id for f in form_list]
    )

    candidates: list[EvaluationFormSnapshotDTO] = []
    for form_def in form_list:
        try:
            candidate_dto = build_evaluation_form_snapshot(
                evaluation_id=evaluation_id,
                form=form_def,
            )
        except (ValidationError, ValueError) as exc:
            raise SnapshotIntegrityError(
                "Failed to build candidate evaluation form snapshot"
            ) from exc

        try:
            verify_evaluation_form_snapshot(
                snapshot_id=candidate_dto.snapshot_id,
                evaluation_id=candidate_dto.evaluation_id,
                agent_id=candidate_dto.agent_id,
                rubric_set_id=candidate_dto.rubric_set_id,
                adapter_key=candidate_dto.adapter_key,
                adapter_version=candidate_dto.adapter_version,
                snapshot_hash=candidate_dto.snapshot_hash,
                snapshot_payload=candidate_dto.snapshot_payload.model_dump(mode="json"),
            )
        except (ValidationError, ValueError) as exc:
            raise SnapshotIntegrityError(
                "Candidate evaluation form snapshot failed pure verification"
            ) from exc

        try:
            report = validate_form_definition(candidate_dto.form)
        except (ValidationError, ValueError) as exc:
            raise SnapshotIntegrityError(
                "Candidate form definition validation failed against manifest/budget"
            ) from exc

        if not report.is_valid:
            raise SnapshotIntegrityError(
                "Candidate form definition failed deployed budget validation"
            )
        candidates.append(candidate_dto)

    records = [
        {
            "snapshot_id": c.snapshot_id,
            "evaluation_id": c.evaluation_id,
            "agent_id": c.agent_id,
            "rubric_set_id": c.rubric_set_id,
            "snapshot_payload": c.snapshot_payload.model_dump(mode="json"),
            "snapshot_hash": c.snapshot_hash,
            "adapter_key": c.adapter_key,
            "adapter_version": c.adapter_version,
        }
        for c in candidates
    ]

    bind = session.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "sqlite":
        stmt = sqlite_insert(EvaluationFormSnapshot).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["evaluation_id", "agent_id"])
        session.execute(stmt)
    elif dialect_name == "postgresql":
        stmt = pg_insert(EvaluationFormSnapshot).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["evaluation_id", "agent_id"])
        session.execute(stmt)
    else:
        raise SnapshotIntegrityError("Unsupported database dialect")

    session.flush()

    readback_rows = (
        session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=evaluation_id)
        .all()
    )

    readback_dtos = _verify_snapshot_row_set(readback_rows, agents_tuple, evaluation_id)

    candidate_map = {c.agent_id: c for c in candidates}
    for dto in readback_dtos:
        cand = candidate_map[dto.agent_id]
        if (
            dto.evaluation_id != cand.evaluation_id
            or dto.agent_id != cand.agent_id
            or dto.rubric_set_id != cand.rubric_set_id
            or dto.adapter_key != cand.adapter_key
            or dto.adapter_version != cand.adapter_version
            or dto.snapshot_hash != cand.snapshot_hash
            or dto.snapshot_payload != cand.snapshot_payload
        ):
            raise SnapshotIntegrityError(
                "Snapshot mismatch between candidate and readback row"
            )

    return readback_dtos


def resolve_or_reuse_evaluation_snapshots(
    session: Session,
    evaluation_id: uuid.UUID,
    scheduled_agent_ids: Sequence[str],
) -> tuple[EvaluationFormSnapshotDTO, ...]:
    """Resolve active forms into immutable snapshots or reuse existing snapshots.

    If any snapshots exist for the evaluation, exact scheduled set is required
    and reused. If none exist, active forms are bulk-loaded, candidates built and
    verified, inserted via conflict-safe dialect insert, flushed, read back, and
    verified.
    """
    if not isinstance(evaluation_id, uuid.UUID):
        raise SnapshotIntegrityError("evaluation_id must be a valid UUID")

    agents_tuple = _normalize_and_validate_scheduled_agents(scheduled_agent_ids)

    existing_rows = (
        session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=evaluation_id)
        .all()
    )

    if existing_rows:
        return _verify_snapshot_row_set(existing_rows, agents_tuple, evaluation_id)

    # None exist: load active forms
    try:
        active_forms = load_active_form_definitions(session, agents_tuple)
    except (ValueError, LookupError) as exc:
        raise SnapshotIntegrityError(
            "Failed to load active form definitions for scheduled agents"
        ) from exc

    ordered_forms = [active_forms[agent_id] for agent_id in agents_tuple]
    return persist_evaluation_form_snapshots(session, evaluation_id, ordered_forms)


__all__ = [
    "load_verified_evaluation_snapshots",
    "persist_evaluation_form_snapshots",
    "resolve_or_reuse_evaluation_snapshots",
]
