"""apps/server/modules/training_data/host_keys.py"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from server.modules.training_data.exceptions import HostKeyInvalidError
from server.modules.training_data.models import (
    AgentAdapterPublication,
    HostSyncKey,
    TrainedAdapter,
)
from server.modules.training_data.schemas import HostManifestEntry
from server.modules.training_data.serving import gguf_filename
from server.modules.training_data.tokens import generate_raw_token, hash_token
from sqlalchemy.orm import Session

KEY_PREFIX = "hsk_"


def create_host_key(session: Session, created_by: uuid.UUID) -> tuple[HostSyncKey, str]:
    """Create the one active key (revoking any older one); return the raw key once."""
    now = datetime.now(UTC)
    session.query(HostSyncKey).filter(HostSyncKey.revoked_at.is_(None)).update(
        {"revoked_at": now}, synchronize_session=False
    )
    raw = KEY_PREFIX + generate_raw_token()
    row = HostSyncKey(
        key_id=uuid.uuid4(),
        key_hash=hash_token(raw),
        created_by=created_by,
        created_at=now,
    )
    session.add(row)
    session.commit()
    return row, raw


def get_active_key(session: Session) -> HostSyncKey | None:
    return (
        session.query(HostSyncKey)
        .filter(HostSyncKey.revoked_at.is_(None))
        .order_by(HostSyncKey.created_at.desc())
        .first()
    )


def revoke_host_key(session: Session) -> bool:
    count = (
        session.query(HostSyncKey)
        .filter(HostSyncKey.revoked_at.is_(None))
        .update({"revoked_at": datetime.now(UTC)}, synchronize_session=False)
    )
    session.commit()
    return count > 0


def authenticate_host_key(session: Session, raw_key: str | None) -> HostSyncKey:
    """Return the active key row for raw_key and record that the host called."""
    if not raw_key:
        raise HostKeyInvalidError("missing host key")
    wanted = hash_token(raw_key)
    row = get_active_key(session)
    if row is None or not secrets.compare_digest(row.key_hash, wanted):
        raise HostKeyInvalidError("invalid host key")
    row.last_seen_at = datetime.now(UTC)
    session.commit()
    return row


def list_host_manifest(session: Session) -> list[HostManifestEntry]:
    published = {
        p.agent_id: p.adapter_id for p in session.query(AgentAdapterPublication).all()
    }
    rows = (
        session.query(TrainedAdapter)
        .filter(TrainedAdapter.gguf_storage_key.isnot(None))
        .order_by(TrainedAdapter.agent_id, TrainedAdapter.version)
        .all()
    )
    return [
        HostManifestEntry(
            adapter_id=a.adapter_id,
            agent_id=a.agent_id,
            version=a.version,
            filename=gguf_filename(a.agent_id, a.version),
            sha256=a.gguf_sha256 or "",
            size_bytes=a.gguf_size_bytes or 0,
            published=published.get(a.agent_id) == a.adapter_id,
        )
        for a in rows
    ]
