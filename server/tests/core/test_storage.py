"""Unit tests for the storage backend abstraction (Local and Cloudflare R2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from server.core.storage import (
    LocalStorageBackend,
    R2StorageBackend,
    extract_document_filename,
    get_storage_backend,
    reset_storage_backend_for_tests,
)


def test_extract_document_filename_handles_various_paths():
    uuid_str = "b9e8ec75-f591-4c0e-9ff9-2eaa9bfb58c0"
    expected = f"{uuid_str}.pdf"

    # Windows path
    win_path = rf"C:\Users\Admin\Desktop\EquipED\uploads\{uuid_str}.pdf"
    assert extract_document_filename(win_path) == expected

    # macOS path
    mac_path = f"/Users/admin/Developer/repos/EquipED/uploads/{uuid_str}.pdf"
    assert extract_document_filename(mac_path) == expected

    # Linux temp pytest path
    temp_path = f"/tmp/pytest-123/{uuid_str}.pdf"
    assert extract_document_filename(temp_path) == expected

    # R2 URI
    r2_uri = f"r2://my-bucket/documents/{uuid_str}.pdf"
    assert extract_document_filename(r2_uri) == expected

    # Plain filename
    assert extract_document_filename(f"{uuid_str}.pdf") == expected


def test_local_storage_backend(tmp_path: Path):
    storage = LocalStorageBackend(tmp_path)

    # Upload bytes
    data = b"%PDF-1.4 test document content"
    ref = storage.upload_bytes("doc-123.pdf", data)
    assert Path(ref).exists()
    assert storage.file_exists("doc-123.pdf")

    # Get file bytes
    assert storage.get_file_bytes("doc-123.pdf") == data

    # Stream
    stream, size, media_type = storage.get_file_stream("doc-123.pdf")
    assert size == len(data)
    assert media_type == "application/pdf"
    chunks = list(stream)
    assert b"".join(chunks) == data

    # Download
    download_dest = tmp_path / "downloads" / "downloaded.pdf"
    downloaded = storage.download_file("doc-123.pdf", download_dest)
    assert downloaded.exists()
    assert downloaded.read_bytes() == data

    # Delete
    assert storage.delete_file("doc-123.pdf")
    assert not storage.file_exists("doc-123.pdf")


def test_r2_storage_backend_mocked():
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        storage = R2StorageBackend(
            endpoint_url="https://account.r2.cloudflarestorage.com",
            access_key_id="test-key",
            secret_access_key="test-secret",
            bucket_name="equiped-bucket",
        )

        # Upload
        data = b"%PDF-1.4 cloud test"
        ref = storage.upload_bytes("11111111-2222-3333-4444-555555555555.pdf", data)
        assert (
            ref
            == "r2://equiped-bucket/documents/11111111-2222-3333-4444-555555555555.pdf"
        )
        mock_s3.put_object.assert_called_once()

        # Stream
        body_mock = MagicMock()
        body_mock.read.side_effect = [data, b""]
        mock_s3.get_object.return_value = {
            "Body": body_mock,
            "ContentLength": len(data),
            "ContentType": "application/pdf",
        }
        stream, size, media_type = storage.get_file_stream(ref)
        assert size == len(data)
        assert media_type == "application/pdf"
        assert b"".join(list(stream)) == data

        # Check existence
        mock_s3.head_object.return_value = {}
        assert storage.file_exists(ref)

        # Delete
        assert storage.delete_file(ref)
        mock_s3.delete_object.assert_called_once()


def test_get_storage_backend_fallback_to_local(monkeypatch, tmp_path):
    reset_storage_backend_for_tests()

    backend = get_storage_backend()
    assert isinstance(backend, LocalStorageBackend)
    reset_storage_backend_for_tests()
