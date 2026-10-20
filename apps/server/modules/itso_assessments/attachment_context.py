"""Frozen, local-only attachment identities for historical integrity checks.

Reads use recorded IDs, so later attachments cannot change a saved assessment.
"""

from __future__ import annotations

import json
from uuid import UUID

from equiped_harness.agents.itso.compatibility.contracts import ITSO_CRITERION_IDS
from sqlalchemy import select

from server.modules.documents.source_artifact_service import load_owned_source_snapshot
from server.modules.documents.source_artifacts import DocumentSourceSnapshot
from server.modules.evaluations.exceptions import ITSOError

from .policy_service import checked_policy, digest
from .workflow_models import DocumentAttachment, PolicyApproval

_CRITERIA = {
    "license": ("ITSO-01", "ITSO-05"),
    "reference": ("ITSO-02",),
    "ownership": ("ITSO-03", "ITSO-05"),
    "privacy": ("ITSO-04",),
    "permission": ("ITSO-05",),
    "rights": ("ITSO-05",),
}


def _record(db, row):
    artifact = db.get(DocumentSourceSnapshot, row.source_snapshot_id)
    if artifact is None or row.kind not in _CRITERIA:
        raise ITSOError("attachment_integrity_error")
    policy = (
        checked_policy(db, row.policy_version_id) if row.policy_version_id else None
    )
    if policy and (
        policy.source_snapshot_id != row.source_snapshot_id
        or policy.source_hash != row.source_hash
    ):
        raise ITSOError("attachment_integrity_error")
    if row.visibility == "owned":
        if artifact.owner_id != row.owner_id:
            raise ITSOError("attachment_integrity_error")
    elif row.visibility == "approved_reference":
        if not (
            row.kind == "reference"
            and policy
            and policy.kind == "institutional"
            and policy.payload.get("visibility") == "approved_reference"
            and db.scalar(
                select(PolicyApproval.approval_id).where(
                    PolicyApproval.policy_version_id == policy.policy_version_id,
                    PolicyApproval.decision == "approve",
                )
            )
        ):
            raise ITSOError("attachment_integrity_error")
    else:
        raise ITSOError("attachment_integrity_error")
    try:
        source = load_owned_source_snapshot(
            db,
            snapshot_id=row.source_snapshot_id,
            document_id=artifact.document_id,
            owner_id=artifact.owner_id,
        )
    except (LookupError, ValueError) as exc:
        raise ITSOError("attachment_integrity_error") from exc
    if source.source_hash != row.source_hash:
        raise ITSOError("attachment_integrity_error")
    identity = {
        "id": str(row.attachment_id),
        "hash": row.source_hash,
        "source_snapshot_id": str(row.source_snapshot_id),
        "source_document_id": str(artifact.document_id),
        "source_owner_id": str(artifact.owner_id),
        "kind": row.kind,
        "visibility": row.visibility,
        "policy_version_id": str(row.policy_version_id) if policy else None,
        "policy_payload_hash": policy.payload_hash if policy else None,
        "raw_pdf_hash": source.raw_pdf_hash,
        "inventory_hash": artifact.inventory_hash,
    }
    context = json.dumps(
        identity
        | {
            "namespace": "attachment_record",
            "source_id": str(row.source_snapshot_id),
            "source_hash": source.source_hash,
            "canonical_text": source.canonical_text,
            "source_pages": [p.model_dump(mode="json") for p in source.pages],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return identity, context


def attachment_scope_hash(policy_hash, manifest):
    return digest({"policy_hash": policy_hash, "attachments": manifest})


def frozen_attachment_contexts(db, auth):
    """Verify exact frozen identities, not today's mutable active membership."""
    try:
        manifest = auth.manifest["disclosure"]["attachments"]
        if not isinstance(manifest, list):
            raise ValueError("invalid manifest")
        ids = [UUID(item["id"]) for item in manifest]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate attachment")
        contexts = {key: [] for key in ITSO_CRITERION_IDS}
        for item, attachment_id in zip(manifest, ids, strict=True):
            row = db.get(DocumentAttachment, attachment_id)
            if row is None or (row.document_id, row.owner_id) != (
                auth.document_id,
                auth.actor_id,
            ):
                raise ValueError("attachment scope mismatch")
            identity, context = _record(db, row)
            if identity != item:
                raise ValueError("attachment identity mismatch")
            for criterion in _CRITERIA[row.kind]:
                contexts[criterion].append(context)
        return contexts
    except (KeyError, TypeError, ValueError, ITSOError) as exc:
        raise ITSOError("assessment_integrity_failed") from exc
