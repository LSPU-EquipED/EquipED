"""Store, validate and hand out the GGUF file of a trained adapter."""

from __future__ import annotations

import hashlib
import logging
import secrets
import tempfile
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO

from server.core.storage import get_storage_backend
from server.modules.training_data.exceptions import (
    GgufAlreadyExistsError,
    GgufInUseError,
    GgufNotFoundError,
    GgufUploadError,
)
from server.modules.training_data.jobs import _utc
from server.modules.training_data.models import TrainedAdapter
from server.modules.training_data.paths import MAX_ADAPTER_UPLOAD_BYTES
from server.modules.training_data.serving import gguf_filename
from server.modules.training_data.tokens import generate_raw_token, hash_token
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GGUF_MAGIC = b"GGUF"
MAX_GGUF_BYTES = MAX_ADAPTER_UPLOAD_BYTES
GGUF_UPLOAD_TOKEN_TTL = timedelta(hours=24)
_CHUNK = 1024 * 1024


def gguf_storage_key(adapter: TrainedAdapter) -> str:
    """Server-built key; user input never becomes part of it."""
    return (
        f"adapters/{adapter.agent_id}/{adapter.adapter_id}/"
        f"{gguf_filename(adapter.agent_id, adapter.version)}"
    )


def _safe_rollback(session: Session) -> None:
    """Roll back, but never let a dead connection mask the real error."""
    try:
        session.rollback()
    except Exception:
        logger.warning("rollback failed", exc_info=True)


def _clear_metadata(adapter: TrainedAdapter) -> None:
    adapter.gguf_storage_key = None
    adapter.gguf_sha256 = None
    adapter.gguf_size_bytes = None
    adapter.gguf_uploaded_at = None


def store_gguf(
    session: Session,
    adapter: TrainedAdapter,
    source: BinaryIO,
    *,
    replace: bool = False,
    token: str | None = None,
    storage: Any = None,
) -> TrainedAdapter:
    """Validate and store the GGUF; metadata is written only after success."""
    if adapter.gguf_storage_key and not replace:
        raise GgufAlreadyExistsError("adapter already has a GGUF file")
    storage = storage or get_storage_backend()

    digest = hashlib.sha256()
    total = 0
    with tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024) as tmp:
        try:
            while True:
                chunk = source.read(_CHUNK)
                if not chunk:
                    break
                if total == 0 and not chunk.startswith(GGUF_MAGIC):
                    raise GgufUploadError("not a GGUF file")
                total += len(chunk)
                if total > MAX_GGUF_BYTES:
                    raise GgufUploadError("GGUF file is too large")
                digest.update(chunk)
                tmp.write(chunk)
        except OSError as exc:
            raise GgufUploadError("could not read the uploaded file") from exc
        if total <= len(GGUF_MAGIC):
            raise GgufUploadError("not a GGUF file")

        # Re-read under a row lock: another request may have finished (or used
        # the one-time token) while this body was being buffered.
        session.refresh(adapter, with_for_update=True)
        if token is not None and not verify_gguf_upload_token(adapter, token):
            _safe_rollback(session)
            raise GgufNotFoundError("invalid or expired upload token")
        if adapter.gguf_storage_key and not replace:
            _safe_rollback(session)
            raise GgufAlreadyExistsError("adapter already has a GGUF file")

        key = gguf_storage_key(adapter)
        created_here = not adapter.gguf_storage_key
        tmp.seek(0)
        storage.put_artifact(key, tmp, "application/octet-stream")

    adapter.gguf_storage_key = key
    adapter.gguf_sha256 = digest.hexdigest()
    adapter.gguf_size_bytes = total
    adapter.gguf_uploaded_at = datetime.now(UTC)
    adapter.gguf_upload_token_hash = None
    adapter.gguf_upload_expires_at = None
    try:
        session.commit()
    except Exception:
        _safe_rollback(session)
        if created_here:
            storage.delete_artifact(key)
        else:
            logger.error(
                "GGUF replace for adapter %s failed to commit; the stored file "
                "no longer matches the recorded sha256 and the upload must be "
                "retried",
                adapter.adapter_id,
            )
        raise
    return adapter


def remove_gguf(
    session: Session,
    adapter: TrainedAdapter,
    *,
    published_adapter_id: uuid.UUID | None,
    storage: Any = None,
) -> None:
    if not adapter.gguf_storage_key:
        raise GgufNotFoundError("adapter has no GGUF file")
    if published_adapter_id is not None and published_adapter_id == adapter.adapter_id:
        raise GgufInUseError("the published adapter's GGUF cannot be removed")
    storage = storage or get_storage_backend()
    key = adapter.gguf_storage_key
    # Commit first: a failed commit must never leave metadata pointing at a
    # deleted file. An orphaned object is the lesser evil.
    _clear_metadata(adapter)
    session.commit()
    try:
        deleted = storage.delete_artifact(key)
    except Exception:
        logger.warning("could not delete GGUF object %s", key, exc_info=True)
    else:
        if deleted is False:
            logger.warning("could not delete GGUF object %s (not removed)", key)


def issue_gguf_upload_token(session: Session, adapter: TrainedAdapter) -> str:
    raw = generate_raw_token()
    adapter.gguf_upload_token_hash = hash_token(raw)
    adapter.gguf_upload_expires_at = datetime.now(UTC) + GGUF_UPLOAD_TOKEN_TTL
    session.commit()
    return raw


def verify_gguf_upload_token(adapter: TrainedAdapter, raw_token: str) -> bool:
    if adapter.gguf_storage_key:
        return False
    if not adapter.gguf_upload_token_hash or adapter.gguf_upload_expires_at is None:
        return False
    if _utc(adapter.gguf_upload_expires_at) < datetime.now(UTC):
        return False
    return secrets.compare_digest(adapter.gguf_upload_token_hash, hash_token(raw_token))


def build_download_link(
    adapter: TrainedAdapter, *, expires_in_seconds: int, storage: Any = None
) -> str | None:
    """Presigned URL, or None when the backend cannot presign (use streaming)."""
    if not adapter.gguf_storage_key:
        raise GgufNotFoundError("adapter has no GGUF file")
    storage = storage or get_storage_backend()
    if not storage.artifact_exists(adapter.gguf_storage_key):
        raise GgufNotFoundError("the GGUF file is missing from storage")
    return storage.presign_artifact(
        adapter.gguf_storage_key,
        expires_in=expires_in_seconds,
        download_filename=gguf_filename(adapter.agent_id, adapter.version),
    )


def open_gguf_stream(
    adapter: TrainedAdapter, storage: Any = None
) -> tuple[Generator[bytes, None, None], int | None]:
    if not adapter.gguf_storage_key:
        raise GgufNotFoundError("adapter has no GGUF file")
    storage = storage or get_storage_backend()
    try:
        return storage.open_artifact(adapter.gguf_storage_key)
    except Exception as exc:  # FileNotFoundError locally, ClientError on R2
        logger.warning(
            "GGUF object %s could not be opened",
            adapter.gguf_storage_key,
            exc_info=True,
        )
        raise GgufNotFoundError("the GGUF file is missing from storage") from exc
