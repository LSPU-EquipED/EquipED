"""Unit tests for the storage backend abstraction (Local and Cloudflare R2)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
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
    from dataclasses import replace

    from server.core.config import get_settings

    local_settings = replace(
        get_settings(),
        storage_backend="local",
        r2_access_key_id=None,
        r2_secret_access_key=None,
    )
    monkeypatch.setattr("server.core.storage.get_settings", lambda: local_settings)
    reset_storage_backend_for_tests()

    backend = get_storage_backend()
    assert isinstance(backend, LocalStorageBackend)
    reset_storage_backend_for_tests()


def test_local_artifact_roundtrip_keeps_directories(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    key = "adapters/sme/abc/sme-v8.gguf"
    assert backend.put_artifact(key, io.BytesIO(b"GGUFdata")) == key
    assert backend.artifact_exists(key) is True
    stream, size = backend.open_artifact(key)
    assert size == 8 and b"".join(stream) == b"GGUFdata"
    expected = tmp_path / "artifacts" / "adapters" / "sme" / "abc" / "sme-v8.gguf"
    assert expected.exists()
    assert backend.delete_artifact(key) is True
    assert backend.artifact_exists(key) is False
    assert backend.delete_artifact(key) is False


_BAD_KEYS = [
    "../x.gguf",
    "adapters/../../x.gguf",
    "/etc/passwd",
    "a\\b.gguf",
    "",
    "a//b.gguf",
]


@pytest.mark.parametrize("bad_key", _BAD_KEYS)
def test_local_artifact_rejects_unsafe_keys(tmp_path, bad_key):
    backend = LocalStorageBackend(tmp_path)
    with pytest.raises(ValueError):
        backend.put_artifact(bad_key, io.BytesIO(b"x"))
    assert not any(tmp_path.rglob("x.gguf"))


def test_local_presign_artifact_is_none(tmp_path):
    assert LocalStorageBackend(tmp_path).presign_artifact("a/b.gguf") is None


def test_base_backend_defaults_do_not_break_existing_subclasses():
    from server.core.storage import StorageBackend

    class Legacy(LocalStorageBackend):
        # Existing subclasses/fakes that predate the artifact API.
        put_artifact = StorageBackend.put_artifact
        presign_artifact = StorageBackend.presign_artifact

    legacy = Legacy(Path("."))
    assert legacy.presign_artifact("k") is None
    with pytest.raises(NotImplementedError):
        legacy.put_artifact("k", io.BytesIO(b"x"))


def _r2_backend():
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        storage = R2StorageBackend(
            endpoint_url="https://account.r2.cloudflarestorage.com",
            access_key_id="k",
            secret_access_key="s",
            bucket_name="equiped-bucket",
        )
    return storage, mock_s3


def test_r2_put_artifact_uses_key_verbatim():
    storage, s3 = _r2_backend()
    key = "adapters/sme/abc/sme-v8.gguf"
    fileobj = io.BytesIO(b"GGUF")
    assert storage.put_artifact(key, fileobj) == key
    args, kwargs = s3.upload_fileobj.call_args
    assert args == (fileobj, "equiped-bucket", key)
    assert kwargs["ExtraArgs"] == {"ContentType": "application/octet-stream"}


def test_r2_presign_artifact_sets_content_disposition():
    storage, s3 = _r2_backend()
    s3.generate_presigned_url.return_value = "https://signed"
    url = storage.presign_artifact("a/b.gguf", 3600, download_filename="sme-v8.gguf")
    assert url == "https://signed"
    kwargs = s3.generate_presigned_url.call_args.kwargs
    assert kwargs["ExpiresIn"] == 3600
    assert kwargs["Params"] == {
        "Bucket": "equiped-bucket",
        "Key": "a/b.gguf",
        "ResponseContentDisposition": 'attachment; filename="sme-v8.gguf"',
    }


def test_r2_presign_artifact_sanitizes_filename():
    storage, s3 = _r2_backend()
    s3.generate_presigned_url.return_value = "https://signed"
    bad = ['a"b/../c\n.gguf', 'a"b/../c\\d\r\n.gguf']
    for name in bad:
        storage.presign_artifact("a/b.gguf", download_filename=name)
    forbidden = ['"', "/", "\\", "\n", "\r"]
    for call in s3.generate_presigned_url.call_args_list:
        disp = call.kwargs["Params"]["ResponseContentDisposition"]
        name = disp.removeprefix('attachment; filename="').removesuffix('"')
        assert not any(c in name for c in forbidden)


def test_r2_artifact_exists_delete_open():
    from botocore.exceptions import ClientError

    storage, s3 = _r2_backend()
    s3.head_object.return_value = {}
    assert storage.artifact_exists("a/b.gguf") is True
    s3.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    assert storage.artifact_exists("a/b.gguf") is False
    assert storage.delete_artifact("a/b.gguf") is True
    s3.delete_object.assert_called_once_with(Bucket="equiped-bucket", Key="a/b.gguf")
    body = MagicMock()
    body.iter_chunks.return_value = iter([b"ab", b"cd"])
    s3.get_object.return_value = {"Body": body, "ContentLength": 4}
    stream, size = storage.open_artifact("a/b.gguf")
    assert size == 4 and b"".join(stream) == b"abcd"


@pytest.mark.parametrize("bad_key", _BAD_KEYS)
def test_r2_artifact_rejects_unsafe_keys(bad_key):
    storage, s3 = _r2_backend()
    with pytest.raises(ValueError):
        storage.put_artifact(bad_key, io.BytesIO(b"x"))
    s3.upload_fileobj.assert_not_called()


_ODD_KEYS = [
    "C:/x.gguf",
    "a/b:stream.gguf",
    "a/b" + chr(0) + ".gguf",
    "a/b" + chr(10) + ".gguf",
    "a/b" + chr(127) + ".gguf",
]


@pytest.mark.parametrize("bad_key", _ODD_KEYS)
def test_local_artifact_rejects_odd_characters(tmp_path, bad_key):
    with pytest.raises(ValueError):
        LocalStorageBackend(tmp_path).put_artifact(bad_key, io.BytesIO(b"x"))


@pytest.mark.parametrize("bad_key", _ODD_KEYS)
def test_r2_artifact_rejects_odd_characters(bad_key):
    storage, s3 = _r2_backend()
    with pytest.raises(ValueError):
        storage.put_artifact(bad_key, io.BytesIO(b"x"))
    s3.upload_fileobj.assert_not_called()


class _FailingReader(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.calls = 0

    def read(self, size: int = -1) -> bytes:
        self.calls += 1
        if self.calls > 1:
            raise OSError("stream broke")
        return super().read(size)


def test_local_put_artifact_failure_leaves_no_target(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    key = "adapters/sme/abc/sme-v8.gguf"
    with pytest.raises(OSError):
        backend.put_artifact(key, _FailingReader(b"GGUFdata"))
    assert backend.artifact_exists(key) is False
    assert not list((tmp_path / "artifacts").rglob("*.part*"))


def test_local_put_artifact_failure_keeps_old_content(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    key = "adapters/sme/abc/sme-v8.gguf"
    backend.put_artifact(key, io.BytesIO(b"OLD"))
    with pytest.raises(OSError):
        backend.put_artifact(key, _FailingReader(b"GGUFdata"))
    assert b"".join(backend.open_artifact(key)[0]) == b"OLD"
    assert not list((tmp_path / "artifacts").rglob("*.part*"))


def test_local_put_artifact_success_leaves_no_temp(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    backend.put_artifact("a/b.gguf", io.BytesIO(b"NEW"))
    assert not list((tmp_path / "artifacts").rglob("*.part*"))
