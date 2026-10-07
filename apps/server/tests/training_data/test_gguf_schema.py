"""GGUF metadata columns and schema fields on trained adapters."""

from __future__ import annotations

from datetime import UTC, datetime

from server.modules.training_data.schemas import (
    TrainedAdapterListItem,
    TrainedAdapterResponse,
    adapter_gguf_info,
)
from server.tests.training_data.conftest import make_adapter


def test_new_adapter_has_no_gguf(db_session, admin_user):
    adapter = make_adapter(db_session, "sme", 1)
    db_session.refresh(adapter)
    assert adapter.gguf_storage_key is None
    assert adapter.gguf_upload_token_hash is None
    assert adapter_gguf_info(adapter) is None


def test_gguf_info_when_present(db_session, admin_user):
    adapter = make_adapter(db_session, "sme", 2)
    adapter.gguf_storage_key = "adapters/sme/x/sme-v2.gguf"
    adapter.gguf_sha256 = "a" * 64
    adapter.gguf_size_bytes = 1234
    adapter.gguf_uploaded_at = datetime(2026, 10, 6, tzinfo=UTC)
    db_session.commit()
    info = adapter_gguf_info(adapter)
    assert info is not None
    assert (info.size_bytes, info.sha256) == (1234, "a" * 64)


def test_partial_gguf_columns_are_treated_as_absent(db_session, admin_user):
    adapter = make_adapter(db_session, "sme", 3)
    adapter.gguf_storage_key = "k"
    db_session.commit()
    assert adapter_gguf_info(adapter) is None


def test_response_defaults_gguf_to_none(db_session, admin_user):
    adapter = make_adapter(db_session, "sme", 4)
    response = TrainedAdapterResponse.model_validate(adapter)
    assert response.gguf is None
    item = TrainedAdapterListItem(
        **response.model_dump(),
        gguf_filename="sme-v4.gguf",
        loaded=None,
        published=False,
    )
    assert item.gguf is None
