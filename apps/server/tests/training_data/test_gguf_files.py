"""Tests for the adapter GGUF service."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime, timedelta

import pytest
from server.modules.training_data import gguf_files
from server.modules.training_data.exceptions import (
    GgufAlreadyExistsError,
    GgufInUseError,
    GgufNotFoundError,
    GgufUploadError,
)
from server.modules.training_data.tokens import hash_token

from .conftest import make_adapter

PAYLOAD = b"GGUF" + b"\x01" * 100


def _key(adapter):
    return f"adapters/sme/{adapter.adapter_id}/sme-v{adapter.version}.gguf"


def _assert_no_metadata(adapter):
    assert adapter.gguf_storage_key is None
    assert adapter.gguf_sha256 is None
    assert adapter.gguf_size_bytes is None
    assert adapter.gguf_uploaded_at is None


def _store(db_session, adapter, storage, body=PAYLOAD, **kwargs):
    return gguf_files.store_gguf(
        db_session, adapter, io.BytesIO(body), storage=storage, **kwargs
    )


def test_store_gguf_happy_path(db_session, admin_user, fake_storage):
    adapter = make_adapter(db_session, "sme", 3)
    gguf_files.issue_gguf_upload_token(db_session, adapter)
    _store(db_session, adapter, fake_storage)
    assert fake_storage.objects == {_key(adapter): PAYLOAD}
    assert gguf_files.gguf_storage_key(adapter) == _key(adapter)
    assert adapter.gguf_storage_key == _key(adapter)
    assert adapter.gguf_sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert adapter.gguf_size_bytes == len(PAYLOAD)
    assert adapter.gguf_uploaded_at is not None
    assert adapter.gguf_upload_token_hash is None
    assert adapter.gguf_upload_expires_at is None


@pytest.mark.parametrize("body", [b"XXXX" + b"\x00" * 50, b"", b"GGUF"])
def test_store_gguf_rejects_bad_content(db_session, admin_user, fake_storage, body):
    adapter = make_adapter(db_session, "sme", 1)
    with pytest.raises(GgufUploadError):
        _store(db_session, adapter, fake_storage, body)
    assert fake_storage.objects == {}
    _assert_no_metadata(adapter)


def test_store_gguf_rejects_oversized(
    db_session, admin_user, fake_storage, monkeypatch
):
    monkeypatch.setattr(gguf_files, "MAX_GGUF_BYTES", 10)
    adapter = make_adapter(db_session, "sme", 1)
    with pytest.raises(GgufUploadError):
        _store(db_session, adapter, fake_storage)
    assert fake_storage.objects == {}
    _assert_no_metadata(adapter)


def test_store_gguf_read_error_stores_nothing(db_session, admin_user, fake_storage):
    class Broken:
        def __init__(self):
            self.calls = 0

        def read(self, n=-1):
            self.calls += 1
            if self.calls == 1:
                return PAYLOAD
            raise OSError("connection reset")

    adapter = make_adapter(db_session, "sme", 1)
    with pytest.raises(GgufUploadError):
        gguf_files.store_gguf(db_session, adapter, Broken(), storage=fake_storage)
    assert fake_storage.objects == {}
    _assert_no_metadata(adapter)


def test_store_gguf_existing_requires_replace(db_session, admin_user, fake_storage):
    adapter = make_adapter(db_session, "sme", 1)
    _store(db_session, adapter, fake_storage)
    other = b"GGUF" + b"\x02" * 50
    with pytest.raises(GgufAlreadyExistsError):
        _store(db_session, adapter, fake_storage, other)
    assert fake_storage.objects[_key(adapter)] == PAYLOAD
    assert adapter.gguf_sha256 == hashlib.sha256(PAYLOAD).hexdigest()

    _store(db_session, adapter, fake_storage, other, replace=True)
    assert fake_storage.objects[_key(adapter)] == other
    assert adapter.gguf_sha256 == hashlib.sha256(other).hexdigest()
    assert adapter.gguf_size_bytes == len(other)


def test_store_gguf_storage_failure_leaves_no_metadata(
    db_session, admin_user, fake_storage
):
    fake_storage.put_error = RuntimeError("r2 down")
    adapter = make_adapter(db_session, "sme", 1)
    with pytest.raises(RuntimeError):
        _store(db_session, adapter, fake_storage)
    _assert_no_metadata(adapter)


def test_remove_gguf(db_session, admin_user, fake_storage):
    adapter = make_adapter(db_session, "sme", 1)
    _store(db_session, adapter, fake_storage)
    gguf_files.remove_gguf(
        db_session, adapter, published_adapter_id=None, storage=fake_storage
    )
    assert fake_storage.objects == {}
    _assert_no_metadata(adapter)


def test_remove_gguf_missing_raises(db_session, admin_user, fake_storage):
    adapter = make_adapter(db_session, "sme", 1)
    with pytest.raises(GgufNotFoundError):
        gguf_files.remove_gguf(
            db_session, adapter, published_adapter_id=None, storage=fake_storage
        )


def test_remove_gguf_refused_for_published(db_session, admin_user, fake_storage):
    adapter = make_adapter(db_session, "sme", 1)
    _store(db_session, adapter, fake_storage)
    with pytest.raises(GgufInUseError):
        gguf_files.remove_gguf(
            db_session,
            adapter,
            published_adapter_id=adapter.adapter_id,
            storage=fake_storage,
        )
    assert _key(adapter) in fake_storage.objects
    assert adapter.gguf_storage_key == _key(adapter)


def test_upload_token_lifecycle(db_session, admin_user, fake_storage):
    adapter = make_adapter(db_session, "sme", 1)
    assert gguf_files.verify_gguf_upload_token(adapter, "anything") is False

    raw = gguf_files.issue_gguf_upload_token(db_session, adapter)
    assert adapter.gguf_upload_token_hash == hash_token(raw)
    expires = adapter.gguf_upload_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    delta = expires - datetime.now(UTC)
    assert timedelta(hours=23, minutes=59) < delta <= timedelta(hours=24)

    assert gguf_files.verify_gguf_upload_token(adapter, raw) is True
    assert gguf_files.verify_gguf_upload_token(adapter, "wrong") is False

    adapter.gguf_upload_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert gguf_files.verify_gguf_upload_token(adapter, raw) is False

    # A stored GGUF invalidates even an otherwise-valid token.
    _store(db_session, adapter, fake_storage)
    adapter.gguf_upload_token_hash = hash_token(raw)
    adapter.gguf_upload_expires_at = datetime.now(UTC) + timedelta(hours=1)
    assert gguf_files.verify_gguf_upload_token(adapter, raw) is False


def test_build_download_link(db_session, admin_user, fake_storage):
    adapter = make_adapter(db_session, "sme", 4)
    with pytest.raises(GgufNotFoundError):
        gguf_files.build_download_link(
            adapter, expires_in_seconds=60, storage=fake_storage
        )

    _store(db_session, adapter, fake_storage)
    url = gguf_files.build_download_link(
        adapter, expires_in_seconds=3600, storage=fake_storage
    )
    assert url == f"https://r2.example/{_key(adapter)}?exp=3600"
    assert fake_storage.presigned == [(_key(adapter), 3600, "sme-v4.gguf")]

    fake_storage.presign_result = None
    assert (
        gguf_files.build_download_link(
            adapter, expires_in_seconds=60, storage=fake_storage
        )
        is None
    )


def test_open_gguf_stream(db_session, admin_user, fake_storage):
    adapter = make_adapter(db_session, "sme", 1)
    with pytest.raises(GgufNotFoundError):
        gguf_files.open_gguf_stream(adapter, storage=fake_storage)
    _store(db_session, adapter, fake_storage)
    chunks, size = gguf_files.open_gguf_stream(adapter, storage=fake_storage)
    assert b"".join(chunks) == PAYLOAD
    assert size == len(PAYLOAD)
