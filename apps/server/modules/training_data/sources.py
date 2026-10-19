"""Reuse frozen packages as training sources; humans remain responsible for labels."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from typing import TYPE_CHECKING

from server.modules.auth.service import require_approved_admin
from server.modules.training_data.agents import validate_agent_id
from server.modules.training_data.contracts import DpoPackageManifest, FrozenJobPackage
from server.modules.training_data.exceptions import InvalidTrainingSourceError
from server.modules.training_data.models import DpoTrainingJob
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from server.modules.training_data.jobs import TrainingJobCreated


def validate_training_package(package: FrozenJobPackage, agent_id: str) -> None:
    validate_agent_id(agent_id)
    try:
        _validate_training_package(package, agent_id)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise InvalidTrainingSourceError(str(exc)) from exc


def _validate_training_package(package: FrozenJobPackage, agent_id: str) -> None:
    manifest = DpoPackageManifest.model_validate(package.manifest_json, strict=True)
    if (
        manifest.agent_id != agent_id
        or manifest.manifest_version != "equiped.dpo-package.v1"
    ):
        raise ValueError("Training package agent or manifest version mismatch")
    for content, checksum, size in (
        (package.pairs_content, manifest.pairs_sha256, manifest.pairs_bytes),
        (
            package.provenance_content,
            manifest.provenance_sha256,
            manifest.provenance_bytes,
        ),
    ):
        raw = content.encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != checksum or len(raw) != size:
            raise ValueError("Training package hash or byte count mismatch")
    pairs = [
        json.loads(line) for line in package.pairs_content.splitlines() if line.strip()
    ]
    provenance = [
        json.loads(line)
        for line in package.provenance_content.splitlines()
        if line.strip()
    ]
    if not pairs or len(pairs) != len(provenance) or len(pairs) != manifest.pair_count:
        raise ValueError("Training package counts mismatch or empty dataset")
    evaluations, reviewers, identities, contracts = set(), set(), set(), set()
    for pair, prov in zip(pairs, provenance, strict=True):
        if not isinstance(pair, dict) or set(pair) != {"prompt", "chosen", "rejected"}:
            raise ValueError(
                "Training pair must contain prompt, chosen and rejected only"
            )
        if any(
            not isinstance(value, str) or not value.strip() for value in pair.values()
        ):
            raise ValueError("Training pair strings must be nonempty")
        if json.loads(pair["chosen"]) == json.loads(pair["rejected"]):
            raise ValueError("Training pair has no meaningful preference")
        if not isinstance(prov, dict) or prov.get("agent_id") != agent_id:
            raise ValueError("Provenance agent mismatch")
        for key in ("generation_id", "evaluation_id", "document_id"):
            uuid.UUID(prov[key])
        if (
            not isinstance(prov.get("pair_id"), str)
            or not prov["pair_id"]
            or prov["pair_id"] in identities
        ):
            raise ValueError("Missing or duplicate pair identity")
        identities.add(prov["pair_id"])
        if prov["pair_id"] != prov["generation_id"]:
            raise ValueError("Provenance pair_id must match generation_id")
        if "created_at" not in prov or (
            prov["created_at"] is not None and not isinstance(prov["created_at"], str)
        ):
            raise ValueError("Invalid or missing provenance created_at")
        for field, key in (
            ("prompt", "prompt_sha256"),
            ("rejected", "response_sha256"),
        ):
            if hashlib.sha256(pair[field].encode()).hexdigest() != prov.get(key):
                raise ValueError(f"Provenance {field} hash mismatch")
        for key in ("model_name", "unit_key", "response_contract_key"):
            if not isinstance(prov.get(key), str) or not prov[key].strip():
                raise ValueError(f"Invalid provenance {key}")
        if (
            type(prov.get("response_contract_version")) is not int
            or prov["response_contract_version"] != 1
        ):
            raise ValueError("Unsupported response contract version")
        if (
            not isinstance(prov.get("criterion_ids"), list)
            or not prov["criterion_ids"]
            or any(not isinstance(c, str) or not c for c in prov["criterion_ids"])
        ):
            raise ValueError("Invalid provenance criterion identities")
        if not isinstance(prov.get("reviewer_ids"), list):
            raise ValueError("Invalid provenance reviewer identities")
        reviewers.update(str(uuid.UUID(r)) for r in prov["reviewer_ids"])
        evaluations.add(prov["evaluation_id"])
        contracts.add(prov["response_contract_key"])
    if (
        len(evaluations) != manifest.evaluation_count
        or len(reviewers) != manifest.reviewer_count
        # Existing exports also list contracts of generations they skipped.
        # Every retained pair must be declared; extra observed contracts are valid.
        or not contracts.issubset(set(manifest.response_contract_keys))
    ):
        raise ValueError("Training package manifest totals mismatch")


def get_active_training_package(
    session: Session, agent_id: str
) -> FrozenJobPackage | None:
    source = session.scalars(
        select(DpoTrainingJob).where(
            DpoTrainingJob.agent_id == agent_id,
            DpoTrainingJob.is_active_training_source.is_(True),
        )
    ).one_or_none()
    if source is None:
        return None
    package = FrozenJobPackage(
        source.pairs_content,
        source.provenance_content,
        copy.deepcopy(source.manifest_json),
    )
    validate_training_package(package, agent_id)
    return package


def set_active_training_source(
    session: Session, agent_id: str, job_id: uuid.UUID | None
) -> None:
    """Caller owns commit/rollback; None restores feedback export."""
    validate_agent_id(agent_id)
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"training-source:{agent_id}"},
        )
    target = session.get(DpoTrainingJob, job_id) if job_id is not None else None
    if job_id is not None:
        if target is None or target.agent_id != agent_id:
            raise ValueError("Training source not found for this agent")
        validate_training_package(
            FrozenJobPackage(
                target.pairs_content, target.provenance_content, target.manifest_json
            ),
            agent_id,
        )
    session.execute(
        update(DpoTrainingJob)
        .where(
            DpoTrainingJob.agent_id == agent_id,
            DpoTrainingJob.is_active_training_source.is_(True),
        )
        .values(is_active_training_source=False)
    )
    session.flush()
    if target is not None:
        target.is_active_training_source = True
        session.flush()


def register_training_source(
    session: Session, agent_id: str, admin_id: uuid.UUID, package: FrozenJobPackage
) -> TrainingJobCreated:
    """Register and activate atomically, preserving all prior packages and feedback."""
    from server.modules.training_data.jobs import create_training_job

    require_approved_admin(session, admin_id)
    validate_training_package(package, agent_id)
    result = create_training_job(
        session, agent_id, admin_id, package=package, commit=False
    )
    set_active_training_source(session, agent_id, result.job.job_id)
    return result
