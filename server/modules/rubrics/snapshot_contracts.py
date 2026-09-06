"""Pure DB-free evaluation form snapshot contracts and hashing."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from typing import Any

from pydantic import Field, ValidationError, field_validator, model_validator

from .contracts import (
    MAX_CODE_LENGTH,
    FormDefinition,
    FrozenContractModel,
    _clean_non_empty_str,
    canonicalize_form,
)
from .manifests import (
    get_agent_manifest,
    validate_form,
)

_HASH_REGEX = r"^[0-9a-f]{64}\Z"
_HASH_PATTERN = re.compile(_HASH_REGEX)


class SnapshotIntegrityError(ValueError):
    """Raised when evaluation form snapshot integrity validation fails."""


class EvaluationFormSnapshotPayload(FrozenContractModel):
    """Immutable, strict payload stored inside an evaluation form snapshot."""

    evaluation_id: uuid.UUID
    rubric_set_id: uuid.UUID
    agent_id: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    adapter_key: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    adapter_version: int = Field(..., ge=1)
    form: FormDefinition

    @field_validator("agent_id")
    @classmethod
    def _validate_agent_id(cls, value: str) -> str:
        return _clean_non_empty_str(value, "agent_id", MAX_CODE_LENGTH)

    @field_validator("adapter_key")
    @classmethod
    def _validate_adapter_key(cls, value: str) -> str:
        return _clean_non_empty_str(value, "adapter_key", MAX_CODE_LENGTH)

    @model_validator(mode="after")
    def _validate_invariants(self) -> EvaluationFormSnapshotPayload:
        if self.agent_id != self.form.agent_id:
            raise ValueError(
                f"Payload agent_id '{self.agent_id}' does not match "
                f"form agent_id '{self.form.agent_id}'"
            )
        if self.rubric_set_id != self.form.rubric_set_id:
            raise ValueError(
                f"Payload rubric_set_id '{self.rubric_set_id}' does not match "
                f"form rubric_set_id '{self.form.rubric_set_id}'"
            )
        if self.adapter_key != self.form.adapter_key:
            raise ValueError(
                f"Payload adapter_key '{self.adapter_key}' does not match "
                f"form adapter_key '{self.form.adapter_key}'"
            )
        if self.adapter_version != self.form.adapter_version:
            raise ValueError(
                f"Payload adapter_version {self.adapter_version} does not match "
                f"form adapter_version {self.form.adapter_version}"
            )
        if self.form.domains != canonicalize_form(self.form).domains:
            raise ValueError(
                "FormDefinition within snapshot payload is not in canonical ordering"
            )
        return self

    @property
    def criterion_codes(self) -> tuple[str, ...]:
        """Return canonical tuple of all criterion codes in the snapshot form."""
        return tuple(
            criterion.criterion_code
            for domain in self.form.domains
            for criterion in domain.criteria
        )

    @property
    def criterion_codes_set(self) -> frozenset[str]:
        """Return frozenset of all criterion codes in the snapshot form."""
        return frozenset(self.criterion_codes)


def serialize_snapshot_payload(payload: EvaluationFormSnapshotPayload) -> bytes:
    """Deterministic UTF-8 JSON serialization of a snapshot payload."""
    data = payload.model_dump(mode="json")
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_snapshot_hash(payload: EvaluationFormSnapshotPayload) -> str:
    """Compute 64-char lowercase SHA-256 hex digest of serialized payload."""
    serialized = serialize_snapshot_payload(payload)
    return hashlib.sha256(serialized).hexdigest()


class EvaluationFormSnapshotDTO(FrozenContractModel):
    """Immutable snapshot DTO with verified duplicated columns and payload hash."""

    snapshot_id: uuid.UUID
    evaluation_id: uuid.UUID
    agent_id: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    rubric_set_id: uuid.UUID
    adapter_key: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    adapter_version: int = Field(..., ge=1)
    snapshot_payload: EvaluationFormSnapshotPayload
    snapshot_hash: str = Field(..., min_length=64, max_length=64)

    @field_validator("agent_id")
    @classmethod
    def _validate_agent_id(cls, value: str) -> str:
        return _clean_non_empty_str(value, "agent_id", MAX_CODE_LENGTH)

    @field_validator("adapter_key")
    @classmethod
    def _validate_adapter_key(cls, value: str) -> str:
        return _clean_non_empty_str(value, "adapter_key", MAX_CODE_LENGTH)

    @field_validator("snapshot_hash")
    @classmethod
    def _validate_hash_format(cls, value: str) -> str:
        if not _HASH_PATTERN.fullmatch(value):
            raise ValueError(
                "snapshot_hash must be a 64-character lowercase SHA-256 hex digest"
            )
        return value

    @model_validator(mode="after")
    def _validate_invariants(self) -> EvaluationFormSnapshotDTO:
        if self.evaluation_id != self.snapshot_payload.evaluation_id:
            raise ValueError(
                f"DTO evaluation_id '{self.evaluation_id}' does not match "
                f"payload evaluation_id '{self.snapshot_payload.evaluation_id}'"
            )
        if self.agent_id != self.snapshot_payload.agent_id:
            raise ValueError(
                f"DTO agent_id '{self.agent_id}' does not match "
                f"payload agent_id '{self.snapshot_payload.agent_id}'"
            )
        if self.rubric_set_id != self.snapshot_payload.rubric_set_id:
            raise ValueError(
                f"DTO rubric_set_id '{self.rubric_set_id}' does not match "
                f"payload rubric_set_id '{self.snapshot_payload.rubric_set_id}'"
            )
        if self.adapter_key != self.snapshot_payload.adapter_key:
            raise ValueError(
                f"DTO adapter_key '{self.adapter_key}' does not match "
                f"payload adapter_key '{self.snapshot_payload.adapter_key}'"
            )
        if self.adapter_version != self.snapshot_payload.adapter_version:
            raise ValueError(
                f"DTO adapter_version {self.adapter_version} does not match "
                f"payload adapter_version {self.snapshot_payload.adapter_version}"
            )
        expected_hash = compute_snapshot_hash(self.snapshot_payload)
        if self.snapshot_hash != expected_hash:
            raise ValueError(
                "snapshot_hash does not match recomputed payload SHA-256 hash"
            )
        return self

    @property
    def payload(self) -> EvaluationFormSnapshotPayload:
        return self.snapshot_payload

    @property
    def form(self) -> FormDefinition:
        return self.snapshot_payload.form

    @property
    def criterion_codes(self) -> tuple[str, ...]:
        """Return canonical tuple of all criterion codes in the snapshot form."""
        return self.snapshot_payload.criterion_codes

    @property
    def criterion_codes_set(self) -> frozenset[str]:
        """Return frozenset of all criterion codes in the snapshot form."""
        return self.snapshot_payload.criterion_codes_set


def build_evaluation_form_snapshot(
    evaluation_id: uuid.UUID,
    form: FormDefinition,
    snapshot_id: uuid.UUID | None = None,
) -> EvaluationFormSnapshotDTO:
    """Build a canonically ordered, hashed EvaluationFormSnapshotDTO."""
    canonical_form = canonicalize_form(form)
    payload = EvaluationFormSnapshotPayload(
        evaluation_id=evaluation_id,
        rubric_set_id=canonical_form.rubric_set_id,
        agent_id=canonical_form.agent_id,
        adapter_key=canonical_form.adapter_key,
        adapter_version=canonical_form.adapter_version,
        form=canonical_form,
    )
    snapshot_hash = compute_snapshot_hash(payload)
    sid = snapshot_id if snapshot_id is not None else uuid.uuid4()
    return EvaluationFormSnapshotDTO(
        snapshot_id=sid,
        evaluation_id=evaluation_id,
        agent_id=canonical_form.agent_id,
        rubric_set_id=canonical_form.rubric_set_id,
        adapter_key=canonical_form.adapter_key,
        adapter_version=canonical_form.adapter_version,
        snapshot_payload=payload,
        snapshot_hash=snapshot_hash,
    )


def verify_evaluation_form_snapshot(
    snapshot_id: uuid.UUID,
    evaluation_id: uuid.UUID,
    agent_id: str,
    rubric_set_id: uuid.UUID,
    adapter_key: str,
    adapter_version: int,
    snapshot_hash: str,
    snapshot_payload: Mapping[str, Any],
) -> EvaluationFormSnapshotDTO:
    """Verify an untrusted evaluation form snapshot row against pure integrity rules."""
    if not isinstance(snapshot_payload, Mapping):
        raise SnapshotIntegrityError(
            "Evaluation form snapshot payload must be a valid mapping"
        )

    try:
        payload = EvaluationFormSnapshotPayload.model_validate(snapshot_payload)
    except ValidationError as exc:
        raise SnapshotIntegrityError(
            "Evaluation form snapshot payload failed schema or canonical validation"
        ) from exc

    if evaluation_id != payload.evaluation_id:
        raise SnapshotIntegrityError(
            "evaluation_id mismatch between row column and snapshot payload"
        )
    if agent_id != payload.agent_id:
        raise SnapshotIntegrityError(
            "agent_id mismatch between row column and snapshot payload"
        )
    if rubric_set_id != payload.rubric_set_id:
        raise SnapshotIntegrityError(
            "rubric_set_id mismatch between row column and snapshot payload"
        )
    if adapter_key != payload.adapter_key:
        raise SnapshotIntegrityError(
            "adapter_key mismatch between row column and snapshot payload"
        )
    if adapter_version != payload.adapter_version:
        raise SnapshotIntegrityError(
            "adapter_version mismatch between row column and snapshot payload"
        )

    try:
        manifest = get_agent_manifest(agent_id, adapter_version)
    except ValueError as exc:
        raise SnapshotIntegrityError(
            f"Unknown agent capability manifest for '{agent_id}'"
        ) from exc

    report = validate_form(payload.form, manifest)
    if not report.is_valid:
        error_codes = ", ".join(i.code for i in report.errors)
        raise SnapshotIntegrityError(
            f"Snapshot form definition failed manifest validation for agent "
            f"'{agent_id}': {error_codes}"
        )

    if not isinstance(snapshot_hash, str) or not _HASH_PATTERN.fullmatch(snapshot_hash):
        raise SnapshotIntegrityError(
            "snapshot_hash must be a 64-character lowercase SHA-256 hex digest"
        )

    expected_hash = compute_snapshot_hash(payload)
    if snapshot_hash != expected_hash:
        raise SnapshotIntegrityError(
            "snapshot_hash does not match recomputed payload SHA-256 hash"
        )

    try:
        return EvaluationFormSnapshotDTO(
            snapshot_id=snapshot_id,
            evaluation_id=evaluation_id,
            agent_id=agent_id,
            rubric_set_id=rubric_set_id,
            adapter_key=adapter_key,
            adapter_version=adapter_version,
            snapshot_payload=payload,
            snapshot_hash=snapshot_hash,
        )
    except ValidationError as exc:
        raise SnapshotIntegrityError(
            "EvaluationFormSnapshotDTO invariant check failed"
        ) from exc


def extract_criterion_codes(
    form_or_payload_or_dto: (
        FormDefinition | EvaluationFormSnapshotPayload | EvaluationFormSnapshotDTO
    ),
) -> tuple[str, ...]:
    """Extract ordered tuple of criterion codes from a form, payload, or DTO."""
    if isinstance(form_or_payload_or_dto, FormDefinition):
        return tuple(
            criterion.criterion_code
            for domain in form_or_payload_or_dto.domains
            for criterion in domain.criteria
        )
    return form_or_payload_or_dto.criterion_codes


def extract_criterion_codes_set(
    form_or_payload_or_dto: (
        FormDefinition | EvaluationFormSnapshotPayload | EvaluationFormSnapshotDTO
    ),
) -> frozenset[str]:
    """Extract frozenset of criterion codes from a form, payload, or snapshot DTO."""
    if isinstance(form_or_payload_or_dto, FormDefinition):
        return frozenset(
            criterion.criterion_code
            for domain in form_or_payload_or_dto.domains
            for criterion in domain.criteria
        )
    return form_or_payload_or_dto.criterion_codes_set


__all__ = [
    "EvaluationFormSnapshotDTO",
    "EvaluationFormSnapshotPayload",
    "SnapshotIntegrityError",
    "build_evaluation_form_snapshot",
    "compute_snapshot_hash",
    "extract_criterion_codes",
    "extract_criterion_codes_set",
    "serialize_snapshot_payload",
    "verify_evaluation_form_snapshot",
]
