"""Storage backend abstraction for local filesystem and Cloudflare R2 object storage.

Provides a unified interface for storing, reading, streaming, and deleting document
PDFs. Supports Cloudflare R2 (S3-compatible) when configured, and falls back to
local filesystem storage under the repository's `uploads/` directory.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Generator
from pathlib import Path
from typing import BinaryIO

from server.core.config import get_settings

logger = logging.getLogger(__name__)

# UUID pattern to extract document ID from foreign paths (Windows/macOS absolute paths)
_UUID_PATTERN = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\.pdf",
    re.IGNORECASE,
)


def extract_document_filename(path_or_key: str | Path) -> str:
    """Extract standard {document_id}.pdf from any path, URI, or alien OS path."""
    raw = str(path_or_key)
    match = _UUID_PATTERN.search(raw)
    if match:
        return f"{match.group(1)}.pdf"
    # Fallback to standard filename
    return Path(raw).name


class StorageBackend(ABC):
    """Abstract interface for document file storage."""

    @abstractmethod
    def upload_file(
        self,
        key: str,
        file_obj: BinaryIO,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload a file and return the canonical storage reference."""
        ...

    @abstractmethod
    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload bytes directly and return the canonical storage reference."""
        ...

    @abstractmethod
    def download_file(self, key: str, target_path: Path) -> Path:
        """Download stored file to a local destination."""
        ...

    @abstractmethod
    def get_file_bytes(self, key: str) -> bytes:
        """Retrieve raw file bytes."""
        ...

    @abstractmethod
    def get_file_stream(
        self,
        key: str,
        chunk_size: int = 65536,
    ) -> tuple[Generator[bytes, None, None], int | None, str]:
        """Return a generator of byte chunks, length, and media type."""
        ...

    @abstractmethod
    def file_exists(self, key: str) -> bool:
        """Check whether the file exists in storage."""
        ...

    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """Delete a file from storage."""
        ...

    @abstractmethod
    def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str | None:
        """Generate a presigned download URL if supported."""
        ...


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage under <repo>/uploads."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_local_path(self, key: str) -> Path:
        # Handle foreign paths by extracting filename
        filename = extract_document_filename(key)
        return self.root_dir / filename

    def upload_file(
        self,
        key: str,
        file_obj: BinaryIO,
        content_type: str = "application/pdf",
    ) -> str:
        target = self._resolve_local_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            file_obj.seek(0)
            while chunk := file_obj.read(65536):
                f.write(chunk)
        return str(target)

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        target = self._resolve_local_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def download_file(self, key: str, target_path: Path) -> Path:
        source = self._resolve_local_path(key)
        if not source.exists():
            raise FileNotFoundError(f"File {key} not found at {source}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source != target_path.resolve():
            import shutil

            shutil.copyfile(source, target_path)
        return target_path

    def get_file_bytes(self, key: str) -> bytes:
        target = self._resolve_local_path(key)
        if not target.exists():
            raise FileNotFoundError(f"File {key} not found at {target}")
        return target.read_bytes()

    def get_file_stream(
        self,
        key: str,
        chunk_size: int = 65536,
    ) -> tuple[Generator[bytes, None, None], int | None, str]:
        target = self._resolve_local_path(key)
        if not target.exists():
            raise FileNotFoundError(f"File {key} not found at {target}")
        size = target.stat().st_size

        def stream() -> Generator[bytes, None, None]:
            with open(target, "rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk

        return stream(), size, "application/pdf"

    def file_exists(self, key: str) -> bool:
        target = self._resolve_local_path(key)
        return target.exists() and target.is_file()

    def delete_file(self, key: str) -> bool:
        target = self._resolve_local_path(key)
        if target.exists():
            target.unlink(missing_ok=True)
            return True
        return False

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str | None:
        return None


class R2StorageBackend(StorageBackend):
    """Cloudflare R2 object storage via boto3 S3 API."""

    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_url: str | None = None,
    ) -> None:
        import boto3
        from botocore.config import Config

        self.bucket_name = bucket_name
        self.public_url = public_url.rstrip("/") if public_url else None
        self.endpoint_url = endpoint_url

        self._s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(
                s3={"addressing_style": "path"},
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def _normalize_key(self, key: str) -> str:
        """Strip URI prefixes and normalize to storage key."""
        clean = key.removeprefix(f"r2://{self.bucket_name}/").removeprefix("r2://")
        # If it's a foreign path, extract {document_id}.pdf
        filename = extract_document_filename(clean)
        return f"documents/{filename}"

    def upload_file(
        self,
        key: str,
        file_obj: BinaryIO,
        content_type: str = "application/pdf",
    ) -> str:
        r2_key = self._normalize_key(key)
        file_obj.seek(0)
        self._s3_client.upload_fileobj(
            file_obj,
            self.bucket_name,
            r2_key,
            ExtraArgs={"ContentType": content_type},
        )
        return f"r2://{self.bucket_name}/{r2_key}"

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        r2_key = self._normalize_key(key)
        self._s3_client.put_object(
            Bucket=self.bucket_name,
            Key=r2_key,
            Body=data,
            ContentType=content_type,
        )
        return f"r2://{self.bucket_name}/{r2_key}"

    def download_file(self, key: str, target_path: Path) -> Path:
        r2_key = self._normalize_key(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        self._s3_client.download_file(self.bucket_name, r2_key, str(target_path))
        return target_path

    def get_file_bytes(self, key: str) -> bytes:
        r2_key = self._normalize_key(key)
        response = self._s3_client.get_object(Bucket=self.bucket_name, Key=r2_key)
        return response["Body"].read()

    def get_file_stream(
        self,
        key: str,
        chunk_size: int = 65536,
    ) -> tuple[Generator[bytes, None, None], int | None, str]:
        r2_key = self._normalize_key(key)
        response = self._s3_client.get_object(Bucket=self.bucket_name, Key=r2_key)
        content_length = response.get("ContentLength")
        body = response["Body"]

        def stream() -> Generator[bytes, None, None]:
            try:
                while chunk := body.read(chunk_size):
                    yield chunk
            finally:
                body.close()

        return stream(), content_length, response.get("ContentType", "application/pdf")

    def file_exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        r2_key = self._normalize_key(key)
        try:
            self._s3_client.head_object(Bucket=self.bucket_name, Key=r2_key)
            return True
        except ClientError:
            return False

    def delete_file(self, key: str) -> bool:
        r2_key = self._normalize_key(key)
        try:
            self._s3_client.delete_object(Bucket=self.bucket_name, Key=r2_key)
            return True
        except Exception:
            logger.warning(
                "Failed to delete %s from R2 bucket %s", r2_key, self.bucket_name
            )
            return False

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str | None:
        r2_key = self._normalize_key(key)
        try:
            url = self._s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": r2_key},
                ExpiresIn=expires_in,
            )
            return str(url)
        except Exception as exc:
            logger.warning("Failed to generate presigned URL for %s: %s", r2_key, exc)
            return None


# Module-level singleton
_STORAGE_BACKEND: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Return the active storage backend singleton."""
    global _STORAGE_BACKEND
    if _STORAGE_BACKEND is not None:
        return _STORAGE_BACKEND

    settings = get_settings()

    if settings.storage_backend.lower() == "r2" or settings.r2_configured:
        endpoint = settings.resolved_r2_endpoint_url
        if (
            endpoint
            and settings.r2_access_key_id
            and settings.r2_secret_access_key
            and settings.r2_bucket_name
        ):
            logger.info(
                "Initializing Cloudflare R2 storage backend (bucket: %s)",
                settings.r2_bucket_name,
            )
            _STORAGE_BACKEND = R2StorageBackend(
                endpoint_url=endpoint,
                access_key_id=settings.r2_access_key_id,
                secret_access_key=settings.r2_secret_access_key,
                bucket_name=settings.r2_bucket_name,
                public_url=settings.r2_public_url,
            )
            return _STORAGE_BACKEND

    # Fallback to local filesystem storage
    from server.modules.documents import paths

    logger.info(
        "Initializing local filesystem storage backend at %s", paths.UPLOAD_ROOT
    )
    _STORAGE_BACKEND = LocalStorageBackend(paths.UPLOAD_ROOT)
    return _STORAGE_BACKEND


def reset_storage_backend_for_tests() -> None:
    """Reset the singleton instance for testing environments."""
    global _STORAGE_BACKEND
    _STORAGE_BACKEND = None
