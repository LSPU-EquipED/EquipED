"""Read-only integrity helpers for policy and attachment history."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from .exceptions import ITSOError
from .workflow_models import PolicyVersion


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def checked_policy(db: Session, version_id: UUID) -> PolicyVersion:
    policy = db.get(PolicyVersion, version_id)
    if policy is None:
        raise ITSOError("policy_not_found", 404)
    if digest(policy.payload) != policy.payload_hash:
        raise ITSOError("policy_integrity_error")
    return policy
