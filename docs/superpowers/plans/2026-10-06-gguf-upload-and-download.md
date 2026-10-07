# GGUF Upload and Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Colab notebook uploads the converted GGUF to the app, the app stores it in object storage, and admins (and the host, through a time-limited link) download the correctly named `<agent>-v<version>.gguf` from the Training Data page.

**Architecture:** An additive "artifact" API on the storage layer (verbatim keys, presigned links with a download file name) holds the file. Four nullable columns plus two token columns on `trained_adapters` hold the metadata and the single-use upload permission. New endpoints (token upload for the notebook, admin upload, download link, local streaming fallback, delete) live in the `training_data` module. The notebook gets one new step inside an existing cell. The admin adapter row shows a GGUF status line with Download, Copy link, Upload and Remove.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, boto3 (R2), pytest; React 18 + TypeScript + Vitest; Jupyter notebook JSON.

**Spec:** `docs/superpowers/specs/2026-10-06-gguf-upload-and-download-design.md`

## Global Constraints

- Backend: ruff (E, F, I, UP), line length 88, Python 3.12, absolute `server.*` imports; run from `apps/` with `uv run --project server ...`. `apps/server/core/` stays infrastructure only (generic storage capability, no business rules).
- Frontend: custom components from `@equiped/ui`, no imports from sibling features.
- **Storage:** the existing document methods (`upload_file`, `_normalize_key`, ...) force every key under `documents/` and flatten directories. Do NOT use them for GGUF files. Add the new additive artifact methods (Task 1) and use only those. Keys are built by the server as `adapters/<agent_id>/<adapter_id>/<agent_id>-v<version>.gguf`; user input never becomes a key.
- GGUF validation: extension `.gguf`, size at most `MAX_ADAPTER_UPLOAD_BYTES` (500 MB), first 4 bytes `GGUF`. A missing or invalid GGUF must never affect training, publishing or benchmarks.
- Upload token: random (`generate_raw_token`), stored hashed (`hash_token`), 24-hour expiry, consumed only after a successful upload; any token failure returns 404 with no detail.
- Download link default 24 hours, maximum 7 days. Delete is refused for the published adapter.
- Do NOT insert or remove notebook cells (tests address cells by index); add the upload step inside the existing last cell (index 17, "download the files").
- Migration is additive; do NOT run `alembic upgrade` against any real database. Chain it after the current single head (`uv run alembic heads` from `apps/server`; currently `20261003_0001`).
- No `Co-Authored-By` or `Claude-Session` trailers in commit messages (CLAUDE.md). Commit per task (the user authorized this feature's commits).
- Work on a new branch `feat/gguf-upload-download` created from the current `origin/main`.

## Review Focus

1. A file with the right extension but wrong magic bytes, an empty file, an oversized file, or a stream that errors halfway: nothing is stored, no metadata is written, the token stays valid (Tasks 3, 4).
2. Path-like or hostile values (a filename with `../`, a different adapter id in the URL, an agent that does not own the adapter): refused with 404, storage key unaffected (Tasks 3, 4).
3. Re-uploading over an existing GGUF without `replace`, deleting the published adapter's file, and a second use of the same token: refused with the right status and no data change (Tasks 3, 4).
4. R2 not configured (local storage) and the presigned URL unavailable: the admin still gets a working admin-only streaming link; the storage artifact keys cannot escape the artifacts folder (Tasks 1, 4).
5. Old adapters with no GGUF and an older backend whose upload response has no `gguf_upload_url`: the list returns `gguf: null`, the UI shows "Not uploaded", the notebook skips its upload step without failing (Tasks 4, 5, 6).

---

### Task 1: Additive artifact API on the storage layer

**Files:**
- Modify: `apps/server/core/storage.py` (`StorageBackend`, `LocalStorageBackend`, `R2StorageBackend`)
- Test: `apps/server/tests/core/test_storage.py`

**Interfaces:**
- Consumes: nothing.
- Produces on `StorageBackend` (non-abstract, default `NotImplementedError`/`None` so existing subclasses and fakes keep working), implemented on both backends:
  - `put_artifact(key: str, file_obj: BinaryIO, content_type: str = "application/octet-stream") -> str` returns the key
  - `artifact_exists(key: str) -> bool`
  - `delete_artifact(key: str) -> bool`
  - `open_artifact(key: str, chunk_size: int = 65536) -> tuple[Generator[bytes, None, None], int | None]`
  - `presign_artifact(key: str, expires_in: int = 86400, download_filename: str | None = None) -> str | None` (`None` for local storage)

- [ ] **Step 1: Write the failing tests**

Follow the existing patterns in `tests/core/test_storage.py` (read how it builds `LocalStorageBackend(tmp_path)` and how it fakes the R2 boto3 client). Add:

```python
import io

import pytest
from server.core.storage import LocalStorageBackend


def test_local_artifact_roundtrip_keeps_directories(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    key = "adapters/sme/abc/sme-v8.gguf"
    assert backend.put_artifact(key, io.BytesIO(b"GGUFdata")) == key
    assert backend.artifact_exists(key) is True
    stream, size = backend.open_artifact(key)
    assert size == 8 and b"".join(stream) == b"GGUFdata"
    assert (tmp_path / "artifacts" / "adapters" / "sme" / "abc" / "sme-v8.gguf").exists()
    assert backend.delete_artifact(key) is True
    assert backend.artifact_exists(key) is False
    assert backend.delete_artifact(key) is False


@pytest.mark.parametrize(
    "bad_key",
    ["../x.gguf", "adapters/../../x.gguf", "/etc/passwd", "a\\b.gguf", "", "a//b.gguf"],
)
def test_local_artifact_rejects_unsafe_keys(tmp_path, bad_key):
    backend = LocalStorageBackend(tmp_path)
    with pytest.raises(ValueError):
        backend.put_artifact(bad_key, io.BytesIO(b"x"))
    assert not any(tmp_path.rglob("x.gguf"))


def test_local_presign_artifact_is_none(tmp_path):
    assert LocalStorageBackend(tmp_path).presign_artifact("a/b.gguf") is None


def test_base_backend_defaults_do_not_break_existing_subclasses():
    from server.core.storage import StorageBackend

    assert StorageBackend.presign_artifact(object.__new__(StorageBackend), "k") is None
```

R2 tests (use the same fake client style as the existing R2 tests; assert on the calls):
- `put_artifact("adapters/sme/abc/sme-v8.gguf", fileobj, ...)` calls `upload_fileobj` with `Key` EXACTLY `adapters/sme/abc/sme-v8.gguf` (no `documents/` prefix) and returns the key.
- `presign_artifact(key, 3600, download_filename="sme-v8.gguf")` calls `generate_presigned_url` with `Params` containing `Bucket`, `Key` and `ResponseContentDisposition == 'attachment; filename="sme-v8.gguf"'`, and `ExpiresIn=3600`.
- A `download_filename` with quotes, slashes or newlines is reduced to `[A-Za-z0-9._-]` characters (e.g. `'a"b/../c\n.gguf'` becomes `a_b_.._c_.gguf` or equivalent safe string; assert no `"`, `/`, `\` or newline remains inside the quoted name).
- Unsafe keys raise `ValueError` for R2 too.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps && uv run --project server pytest server/tests/core/test_storage.py -v -k "artifact or presign_artifact"`
Expected: FAIL (`AttributeError: ... put_artifact`).

- [ ] **Step 3: Implement**

In `core/storage.py` add a module-level helper:

```python
def _validate_artifact_key(key: str) -> str:
    """Return the key unchanged if it is a safe relative object key, else raise."""
    if (
        not key
        or key.startswith("/")
        or "\\" in key
        or "//" in key
        or any(part in ("", ".", "..") for part in key.split("/"))
    ):
        raise ValueError(f"unsafe artifact key: {key!r}")
    return key


def _safe_download_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)
```
(import `re` at the top if missing). On `StorageBackend` add the five methods as plain (non-`@abstractmethod`) methods: `put_artifact`, `artifact_exists`, `delete_artifact`, `open_artifact` raise `NotImplementedError`; `presign_artifact` returns `None`.

`LocalStorageBackend`: artifacts live under `self.root_dir / "artifacts" / key`; resolve and assert the resolved path is inside `root_dir / "artifacts"` (defense in depth after `_validate_artifact_key`); `put_artifact` creates parent directories, copies the file object in 64 KB chunks after `seek(0)`, returns the key; `artifact_exists`, `delete_artifact` (returns False if missing), `open_artifact` (returns generator and size). `presign_artifact` stays the base `None`.

`R2StorageBackend`: use the validated key verbatim. `put_artifact`: `file_obj.seek(0)`, `self._s3_client.upload_fileobj(file_obj, self.bucket_name, key, ExtraArgs={"ContentType": content_type})`, return key. `artifact_exists`: `head_object` (False on `ClientError` 404, like the existing `file_exists`; copy its error handling). `delete_artifact`: `delete_object`, return True (False and a warning log on exception, like `delete_file`). `open_artifact`: `get_object`, generator over `response["Body"].iter_chunks(chunk_size)`, size from `ContentLength`. `presign_artifact`: `Params={"Bucket": ..., "Key": key}` plus, when `download_filename` is given, `"ResponseContentDisposition": f'attachment; filename="{_safe_download_filename(download_filename)}"'`; return `str(url)` or `None` with a warning on exception.

- [ ] **Step 4: Run the tests**

Run: `cd apps && uv run --project server pytest server/tests/core/test_storage.py -v`
Expected: all PASS (existing document-storage tests included).

- [ ] **Step 5: Lint and commit**

Run: `cd apps && uv run --project server ruff check --fix server/core/storage.py server/tests/core/test_storage.py && uv run --project server ruff format server/core/storage.py server/tests/core/test_storage.py`

```bash
git add apps/server/core/storage.py apps/server/tests/core/test_storage.py
git commit -m "feat(storage): add generic artifact storage with presigned downloads"
```

---

### Task 2: Columns, migration and the `gguf` field

**Files:**
- Modify: `apps/server/modules/training_data/models.py` (`TrainedAdapter`)
- Create: `apps/server/alembic/versions/20261006_0001_add_gguf_to_trained_adapters.py`
- Modify: `apps/server/modules/training_data/schemas.py`
- Test: `apps/server/tests/training_data/test_gguf_schema.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `TrainedAdapter` columns `gguf_storage_key: str | None`, `gguf_sha256: str | None`, `gguf_size_bytes: int | None`, `gguf_uploaded_at: datetime | None`, `gguf_upload_token_hash: str | None`, `gguf_upload_expires_at: datetime | None`; schemas `AdapterGgufInfo(size_bytes: int, sha256: str, uploaded_at: datetime)`, `TrainedAdapterResponse.gguf: AdapterGgufInfo | None = None`, `TrainedAdapterUploadResponse(TrainedAdapterResponse)` with `gguf_upload_url: str | None = None`, `GgufDownloadLinkResponse(url: str, filename: str, sha256: str, size_bytes: int, expires_at: datetime)`; helper `adapter_gguf_info(adapter) -> AdapterGgufInfo | None` in `schemas.py`.

- [ ] **Step 1: Write the failing tests**

```python
"""apps/server/tests/training_data/test_gguf_schema.py"""

from __future__ import annotations

from datetime import UTC, datetime

from server.modules.training_data.schemas import (
    TrainedAdapterListItem,
    TrainedAdapterResponse,
    adapter_gguf_info,
)
from server.tests.training_data.conftest import make_adapter


def test_new_adapter_has_no_gguf(db_session):
    adapter = make_adapter(db_session, "sme", 1)
    db_session.refresh(adapter)
    assert adapter.gguf_storage_key is None
    assert adapter.gguf_upload_token_hash is None
    assert adapter_gguf_info(adapter) is None


def test_gguf_info_when_present(db_session):
    adapter = make_adapter(db_session, "sme", 2)
    adapter.gguf_storage_key = "adapters/sme/x/sme-v2.gguf"
    adapter.gguf_sha256 = "a" * 64
    adapter.gguf_size_bytes = 1234
    adapter.gguf_uploaded_at = datetime(2026, 10, 6, tzinfo=UTC)
    db_session.commit()
    info = adapter_gguf_info(adapter)
    assert info is not None
    assert (info.size_bytes, info.sha256) == (1234, "a" * 64)


def test_partial_gguf_columns_are_treated_as_absent(db_session):
    adapter = make_adapter(db_session, "sme", 3)
    adapter.gguf_storage_key = "k"
    db_session.commit()
    assert adapter_gguf_info(adapter) is None


def test_response_defaults_gguf_to_none(db_session):
    adapter = make_adapter(db_session, "sme", 4)
    response = TrainedAdapterResponse.model_validate(adapter)
    assert response.gguf is None
    item = TrainedAdapterListItem(
        **response.model_dump(), gguf_filename="sme-v4.gguf", loaded=None, published=False
    )
    assert item.gguf is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_gguf_schema.py -v`
Expected: FAIL (`AttributeError`/`ImportError`).

- [ ] **Step 3: Implement**

In `models.py`, in `TrainedAdapter` after `size_bytes`:

```python
    gguf_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gguf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gguf_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gguf_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gguf_upload_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    gguf_upload_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

Migration `20261006_0001_add_gguf_to_trained_adapters.py` (same shape as `20261003_0001`, `down_revision` = the current single head), adding the six columns with `op.add_column("trained_adapters", sa.Column(...))` (types: `sa.String(512)`, `sa.String(64)`, `sa.Integer()`, `sa.DateTime(timezone=True)`, `sa.String(64)`, `sa.DateTime(timezone=True)`, all `nullable=True`), and a `downgrade()` dropping them in reverse order.

In `schemas.py`:

```python
class AdapterGgufInfo(BaseModel):
    size_bytes: int
    sha256: str
    uploaded_at: datetime


def adapter_gguf_info(adapter: Any) -> AdapterGgufInfo | None:
    """Metadata of the stored GGUF, or None unless every field is present."""
    if (
        adapter.gguf_storage_key is None
        or adapter.gguf_sha256 is None
        or adapter.gguf_size_bytes is None
        or adapter.gguf_uploaded_at is None
    ):
        return None
    return AdapterGgufInfo(
        size_bytes=adapter.gguf_size_bytes,
        sha256=adapter.gguf_sha256,
        uploaded_at=adapter.gguf_uploaded_at,
    )
```
Add `gguf: AdapterGgufInfo | None = None` to `TrainedAdapterResponse`; add `TrainedAdapterUploadResponse` and `GgufDownloadLinkResponse` as described; export the new names in `__all__`.

- [ ] **Step 4: Run tests and check the migration chain**

Run: `cd apps && uv run --project server pytest server/tests/training_data -q`
Expected: PASS.
Run: `cd apps/server && uv run alembic heads`
Expected: exactly one line, `20261006_0001 (head)`.

- [ ] **Step 5: Lint and commit**

```bash
git add apps/server/modules/training_data/models.py apps/server/modules/training_data/schemas.py apps/server/alembic/versions/20261006_0001_add_gguf_to_trained_adapters.py apps/server/tests/training_data/test_gguf_schema.py
git commit -m "feat(training-data): add GGUF metadata columns and schema fields"
```

---

### Task 3: GGUF service (validate, store, remove, token, link)

**Files:**
- Create: `apps/server/modules/training_data/gguf_files.py`
- Modify: `apps/server/modules/training_data/exceptions.py` (new exceptions)
- Test: `apps/server/tests/training_data/test_gguf_files.py`

**Interfaces:**
- Consumes: storage artifact API (Task 1), columns (Task 2), `generate_raw_token`/`hash_token` (`tokens.py`), `gguf_filename` (`serving.py`), `MAX_ADAPTER_UPLOAD_BYTES` (`paths.py`).
- Produces in `gguf_files.py`:
  - `GGUF_UPLOAD_TOKEN_TTL = timedelta(hours=24)`
  - `gguf_storage_key(adapter) -> str`
  - `store_gguf(session, adapter, source: BinaryIO, *, replace: bool = False, storage=None) -> TrainedAdapter`
  - `remove_gguf(session, adapter, *, published_adapter_id: uuid.UUID | None, storage=None) -> None`
  - `issue_gguf_upload_token(session, adapter) -> str` (raw token)
  - `verify_gguf_upload_token(adapter, raw_token: str) -> bool`
  - `build_download_link(adapter, *, expires_in_seconds: int, storage=None) -> str | None` (`None` means use the local streaming endpoint)
  - exceptions `GgufUploadError(Exception)` (invalid content, HTTP 422), `GgufAlreadyExistsError(Exception)` (409), `GgufNotFoundError(Exception)` (404), `GgufInUseError(Exception)` (409, published).
  - `storage` parameters default to `get_storage_backend()` and exist so tests pass a fake.

- [ ] **Step 1: Write the failing tests**

Use a small fake storage in the test file:

```python
class FakeStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.presigned: list[tuple] = []

    def put_artifact(self, key, file_obj, content_type="application/octet-stream"):
        file_obj.seek(0)
        self.objects[key] = file_obj.read()
        return key

    def artifact_exists(self, key):
        return key in self.objects

    def delete_artifact(self, key):
        return self.objects.pop(key, None) is not None

    def presign_artifact(self, key, expires_in=86400, download_filename=None):
        self.presigned.append((key, expires_in, download_filename))
        return f"https://r2.example/{key}?exp={expires_in}"
```

Tests (use `make_adapter` from the conftest, `db_session`, `io.BytesIO`):
- `store_gguf` with `b"GGUF" + payload` stores under `adapters/sme/<adapter_id>/sme-v<n>.gguf`, sets key, sha256 (verify with `hashlib`), size, `gguf_uploaded_at`, clears the token columns.
- Wrong magic bytes (`b"XXXX..."`), empty body, and a body longer than the limit (monkeypatch the module constant `MAX_GGUF_BYTES` to 10) raise `GgufUploadError`; `FakeStorage.objects` stays empty and the metadata columns stay `None`.
- A source that raises `OSError` mid-read: nothing stored, no metadata.
- Existing GGUF without `replace` raises `GgufAlreadyExistsError`; with `replace=True` the object and metadata are replaced (new sha).
- Storage failure on put (fake raises `RuntimeError`) leaves the metadata `None` and re-raises.
- `remove_gguf`: deletes object and clears the four columns; raises `GgufNotFoundError` if none; raises `GgufInUseError` when `published_adapter_id == adapter.adapter_id` (object untouched).
- Token: `issue_gguf_upload_token` returns a raw token whose hash is stored with an expiry about 24 hours ahead; `verify_gguf_upload_token` is True for it, False for a wrong token, False after expiry (set `gguf_upload_expires_at` to the past), False when a GGUF already exists, False when no token was issued.
- `build_download_link` calls `presign_artifact` with the key, the expiry and `download_filename="sme-v<n>.gguf"` and returns its URL; returns `None` when the fake returns `None`; raises `GgufNotFoundError` when the adapter has no GGUF.

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_gguf_files.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

`exceptions.py`: add the four exception classes (plain `Exception` subclasses, same style as the file).

`gguf_files.py`:

```python
"""Store, validate and hand out the GGUF file of a trained adapter."""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO

from sqlalchemy.orm import Session

from server.core.storage import get_storage_backend
from server.modules.training_data.exceptions import (
    GgufAlreadyExistsError,
    GgufInUseError,
    GgufNotFoundError,
    GgufUploadError,
)
from server.modules.training_data.models import TrainedAdapter
from server.modules.training_data.paths import MAX_ADAPTER_UPLOAD_BYTES
from server.modules.training_data.serving import gguf_filename
from server.modules.training_data.tokens import generate_raw_token, hash_token

GGUF_MAGIC = b"GGUF"
MAX_GGUF_BYTES = MAX_ADAPTER_UPLOAD_BYTES
GGUF_UPLOAD_TOKEN_TTL = timedelta(hours=24)
_CHUNK = 1024 * 1024


def gguf_storage_key(adapter: TrainedAdapter) -> str:
    return (
        f"adapters/{adapter.agent_id}/{adapter.adapter_id}/"
        f"{gguf_filename(adapter.agent_id, adapter.version)}"
    )
```
`store_gguf`: if `adapter.gguf_storage_key` and not `replace` raise `GgufAlreadyExistsError`; copy `source` in 1 MB chunks into `tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)`, hashing as you go; first chunk must start with `GGUF_MAGIC` (and the total must be > 4 bytes) else `GgufUploadError("not a GGUF file")`; if the total exceeds `MAX_GGUF_BYTES` raise `GgufUploadError`; wrap any `OSError` from reading in `GgufUploadError`; then `storage.put_artifact(key, tmp, "application/octet-stream")`; then set the metadata, set `gguf_upload_token_hash = None`, `gguf_upload_expires_at = None`, `session.commit()`; if the commit fails, `session.rollback()`, delete the object only when this call created it (no previous `gguf_storage_key`), re-raise. Return the adapter.

`remove_gguf`, `issue_gguf_upload_token` (sets hash and `now + GGUF_UPLOAD_TOKEN_TTL`, commits, returns the raw token), `verify_gguf_upload_token` (uses `secrets.compare_digest` on the hashes; checks expiry with a timezone-aware compare; False if a GGUF exists), `build_download_link` as in the Interfaces block. Use `datetime.now(UTC)` everywhere.

- [ ] **Step 4: Run tests**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_gguf_files.py -v` then `pytest server/tests/training_data -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
git add apps/server/modules/training_data/gguf_files.py apps/server/modules/training_data/exceptions.py apps/server/tests/training_data/test_gguf_files.py
git commit -m "feat(training-data): store, validate and share an adapter GGUF file"
```

---

### Task 4: Endpoints and the upload link in the zip response

**Files:**
- Modify: `apps/server/modules/training_data/router.py`
- Test: `apps/server/tests/training_data/test_router.py` (new tests; follow the file's helpers `_auth`, `client`, `auth_cookies_admin`)

**Interfaces:**
- Consumes: Task 3 service, Task 2 schemas, `_build_url`, `require_admin`, `get_storage_backend`.
- Produces routes under the existing `/admin/training-data` prefix:
  - `POST /jobs/{job_id}/adapter` now returns `TrainedAdapterUploadResponse` with `gguf_upload_url` and `gguf` (all existing fields unchanged)
  - `POST /adapters/{adapter_id}/gguf?token=...` (multipart `file`; no login) -> `TrainedAdapterResponse` (201)
  - `POST /{agent_id}/adapters/{adapter_id}/gguf?replace=false` (admin; multipart `file`) -> `TrainedAdapterResponse` (201)
  - `POST /{agent_id}/adapters/{adapter_id}/gguf/download-link` (admin; body `{"expires_in_hours": int}`, default 24, 1 to 168) -> `GgufDownloadLinkResponse`
  - `GET /{agent_id}/adapters/{adapter_id}/gguf/file` (admin) -> streamed `application/octet-stream` with `Content-Disposition: attachment; filename="<agent>-v<n>.gguf"`
  - `DELETE /{agent_id}/adapters/{adapter_id}/gguf` (admin) -> 204
  - the list endpoint fills `gguf` for each item.
- Every `{agent_id}/adapters/{adapter_id}` route returns 404 unless the adapter exists and belongs to that agent.
- Status mapping: invalid content/size -> 422; exists without `replace` -> 409; no GGUF -> 404; published -> 409; bad or expired token -> 404 with `detail="not found"`.

- [ ] **Step 1: Write the failing tests**

Use a fake storage: monkeypatch `server.modules.training_data.gguf_files.get_storage_backend` (and anything the router imports) to return a `FakeStorage` (copy the one from Task 3, or move it into `tests/training_data/conftest.py` as a fixture `fake_storage` if both files need it; if you move it, update Task 3's tests accordingly). Tests:
- Zip upload via the existing helpers returns `gguf_upload_url` containing `/admin/training-data/adapters/<adapter_id>/gguf?token=` and the `gguf` field `null`.
- Using that URL (strip the host, call with the test client and a multipart file `b"GGUF" + b"x" * 100`): 201, the list shows `gguf` with the right size and sha; the stored object exists in the fake; the same token a second time returns 404.
- Bad magic: 422, nothing stored, and the same token still works afterwards with a good file.
- Wrong token, expired token, other adapter's id: 404 with `"not found"` detail.
- Admin upload: 201 with admin cookies; 409 on the second upload; 201 with `?replace=true`; a non-admin or anonymous caller gets 401/403 (follow the file's existing auth tests).
- Download link: with the fake returning a URL -> 200 with `url`, `filename == "sme-v1.gguf"`, `sha256`, `size_bytes`, `expires_at` about 24 hours ahead; `expires_in_hours=0` and `169` -> 422; adapter without GGUF -> 404; with the fake returning `None` the response `url` points to `/admin/training-data/sme/adapters/<id>/gguf/file`.
- `GET .../gguf/file` streams the bytes with the `Content-Disposition` header; 404 when absent.
- `DELETE`: 204 and the list shows `gguf: null`; 409 when the adapter is published; 404 when absent.
- Path ownership: calling `/gad/adapters/<sme adapter id>/gguf` returns 404.

- [ ] **Step 2: Run to verify failure**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_router.py -v -k gguf`
Expected: FAIL (404s / missing field).

- [ ] **Step 3: Implement**

In `router.py`:
- Add `request: Request` to `upload_trained_adapter`, change `response_model` to `TrainedAdapterUploadResponse`; after `store_adapter_upload` succeeds call `raw = issue_gguf_upload_token(db, adapter)` and build `gguf_upload_url = _build_url(request, f"/admin/training-data/adapters/{adapter.adapter_id}/gguf?token={raw}")`; wrap this in a try/except that, on any failure, logs a warning and returns `gguf_upload_url=None` (the zip upload already succeeded and must never fail because of this).
- A small helper `_get_owned_adapter(db, agent_id, adapter_id)` that loads the row and raises `HTTPException(404, "not found")` unless it exists with `agent_id == agent_id`.
- The token upload route: load the adapter by id, `verify_gguf_upload_token`, else 404; call `store_gguf(db, adapter, file.file)`; map exceptions to statuses as listed; early reject when `file.size` is known and over the limit (422), like the zip route.
- The remaining admin routes as specified; `download-link` computes `expires_in_seconds = hours * 3600`; the streaming route uses `get_storage_backend().open_artifact(key)` inside a `StreamingResponse`.
- In the list endpoint, pass `gguf=adapter_gguf_info(adapter)` into each `TrainedAdapterListItem(...)`.
- Delete passes `published_adapter_id` from the publication row (use the existing helper the router already uses for `published_id`).

- [ ] **Step 4: Run tests**

Run: `cd apps && uv run --project server pytest server/tests/training_data -q`
Expected: PASS (including all earlier tests).

- [ ] **Step 5: Lint and commit**

```bash
git add apps/server/modules/training_data/router.py apps/server/tests/training_data/test_router.py apps/server/tests/training_data/conftest.py
git commit -m "feat(training-data): GGUF upload, download link and delete endpoints"
```

---

### Task 5: Notebook uploads the GGUF

**Files:**
- Modify (cell contents only): `docs/colab/dpo_training_template.ipynb` cell 10 (keep the response) and cell 17
- Test: `apps/server/tests/training_data/test_notebook_gguf_upload.py`

**Interfaces:**
- Consumes: the zip upload response JSON containing `gguf_upload_url` (Task 4).
- Produces: cell 17 runs `conversion_step("upload the GGUF to EquipED")` before the download step.

- [ ] **Step 1: Write the failing tests**

Follow the pattern of `apps/server/tests/training_data/test_notebook_training_summary.py` and `training/tests/test_dpo_notebook_gguf_cells.py` (load the notebook JSON, exec a cell source with a prepared namespace). Namespace for cell 17 needs: `conversion_step` (copy the real helper's behaviour: a context manager that prints and re-raises, OR extract it from cell 13 as that test file does), `OUTPUT_GGUF` (a tmp file path named `sme-v8.gguf` containing `GGUF` + bytes), `GGUF_OUTPUT_FILES = [OUTPUT_GGUF]`, `upload_response` (a fake with `.json()` returning `{"gguf_upload_url": "https://x/upload?token=t", ...}`), and a fake `requests` module in `sys.modules` whose `post(url, files=None, timeout=None)` records calls. Tests:
- Success: `post` called once with the URL, a `file` tuple whose name is `sme-v8.gguf`, and a numeric `timeout`; output mentions the upload succeeded.
- Retries: first two `post` calls raise `ConnectionError`, third succeeds; exactly 3 calls; no exception escapes.
- All three fail: the step prints a message naming the admin "Upload GGUF" button, does NOT raise, and the following download step still runs.
- Server answers 4xx (fake `raise_for_status` raises): no retry on 4xx, no exception escapes.
- `upload_response.json()` has no `gguf_upload_url`: the step is skipped with a note and `post` is never called.
- `upload_response` missing entirely (NameError path): skipped, no exception.
- Cells count and the indexes used by existing tests are unchanged (`len(cells) == 18`).

- [ ] **Step 2: Run to verify failure**, then **Step 3: edit the notebook** with a round-trip-safe script (CRLF, no trailing newline; same approach as the earlier notebook edit: load, assert `json.dumps(nb, indent=1).replace("\n", "\r\n") == raw`, modify only the two cells' `source`, write back). Prepend this block to cell 17's source (before the existing `with conversion_step("download the files"):`):

```python
with conversion_step("upload the GGUF to EquipED"):
    try:
        _gguf_url = upload_response.json().get("gguf_upload_url")
    except Exception:
        _gguf_url = None
    if not _gguf_url:
        print(
            "No GGUF upload link was returned (older backend?). Skipping the upload; "
            "use the Upload GGUF button on the Training Data page instead."
        )
    else:
        import time

        import requests

        _done = False
        for _attempt in range(1, 4):
            try:
                with open(OUTPUT_GGUF, "rb") as _f:
                    _resp = requests.post(
                        _gguf_url,
                        files={"file": (OUTPUT_GGUF, _f, "application/octet-stream")},
                        timeout=600,
                    )
                if 400 <= _resp.status_code < 500:
                    print(f"EquipED refused the GGUF ({_resp.status_code}); not retrying.")
                    break
                _resp.raise_for_status()
                print(f"Uploaded {OUTPUT_GGUF} to EquipED.")
                _done = True
                break
            except Exception as _exc:
                print(f"GGUF upload attempt {_attempt} failed: {_exc!r}")
                time.sleep(2 * _attempt)
        if not _done:
            print(
                "The GGUF was not uploaded. Your local copy is still downloaded below; "
                "add it later with the Upload GGUF button on the Training Data page."
            )
```
`conversion_step` must not swallow-and-hide errors differently from today; the block above never raises, so it is safe. If cell 10's `upload_response` variable name differs in the notebook, use the real name and say so in the report. Keep cell 10 unchanged except if needed to retain the response object (it already is `upload_response`).

- [ ] **Step 4: Run tests**: `cd apps && uv run --project server pytest server/tests/training_data/test_notebook_gguf_upload.py server/tests/training_data/test_dpo_colab_contract.py server/tests/training_data/test_notebook_training_summary.py ../training/tests -q` (the `training/tests` folder may need its own invocation; run it as the repo does). Expected: PASS, and `git diff --stat docs/colab/dpo_training_template.ipynb` is small.

- [ ] **Step 5: Lint and commit**

```bash
git add docs/colab/dpo_training_template.ipynb apps/server/tests/training_data/test_notebook_gguf_upload.py
git commit -m "feat(colab): upload the converted GGUF to EquipED"
```

---

### Task 6: Admin UI

**Files:**
- Modify: `apps/admin/src/features/training-data/types.ts`, `api/trainingData.api.ts`
- Create: `hooks/useAdapterGguf.ts`, `components/AdapterGgufPanel.tsx`
- Modify: `components/AdapterRow.tsx`, `components/AdapterLoadHint.tsx` (one line pointing to the download), and the short "host" section of `training/serving-lora-adapter.md`
- Test: `components/__tests__/AdapterGgufPanel.test.tsx`, extend `components/__tests__/AdapterRow.test.tsx`

**Interfaces:**
- Consumes: the Task 4 endpoints.
- Produces: `TrainedAdapterItem.gguf?: { size_bytes: number; sha256: string; uploaded_at: string } | null`; `trainingDataApi.createGgufDownloadLink(agentId, adapterId, hours)`, `uploadGguf(agentId, adapterId, file, replace)`, `deleteGguf(agentId, adapterId)`; hooks `useUploadGguf`, `useRemoveGguf`, `useGgufDownloadLink` (all invalidate `['trainedAdapters', agentId]` on settle); `<AdapterGgufPanel adapter published onChanged? />`.

Behavior: the panel shows a "GGUF file" heading. Absent: text "Not uploaded" and an **Upload GGUF** button (hidden file input accepting `.gguf`, progress or spinner text while uploading, an error message on failure that does not crash). Present: size (use the existing `formatSize`), SHA-256 with a copy button, the upload time, and buttons **Download** (requests a link, then navigates the browser to `url`), **Copy download link** (requests a link, copies `url` to the clipboard, shows "Link valid until <time>"), and **Remove file** (asks confirmation; disabled with a title explaining why when the adapter is published). All buttons have accessible names including the version (e.g. "Download sme-v8.gguf").

- [ ] **Step 1: Write the failing tests** (vitest + testing-library; mock `trainingDataApi` like the neighboring tests do): Not-uploaded state shows the Upload button; selecting a file calls `uploadGguf` once and shows an error text when it rejects; the present state shows size, sha and the three buttons; Download calls `createGgufDownloadLink` and sets `window.location.href` (spy on a `navigateTo` helper rather than the real `location`); Copy writes the url to `navigator.clipboard.writeText` and shows the expiry text; Remove asks for confirmation and calls `deleteGguf` only after it; Remove is disabled when `published`; no `undefined`/`NaN` text anywhere; the existing AdapterRow tests (provenance, summary) still pass and `AdapterRow` renders the panel inside the Details area.

- [ ] **Step 2: Run to verify failure**: `cd apps/admin && pnpm exec vitest run src/features/training-data`.

- [ ] **Step 3: Implement** the types, api calls (use `requestJson`; the upload uses `FormData` with the same helper style the app already uses for file uploads, see `documentsApi.uploadDocument` in `libs/api-client`), the hooks, the panel and the row integration. Update `AdapterLoadHint` with one line: "Download the file from this page, put it in the adapters folder and restart the server." Update `training/serving-lora-adapter.md` with a short paragraph describing the Download button and link.

- [ ] **Step 4: Run tests, typecheck, lint**: `cd apps/admin && pnpm exec vitest run src/features/training-data && pnpm exec tsc --noEmit && pnpm exec eslint src/features/training-data`.
Expected: all PASS and clean. Restore unrelated files that tooling rewrites (line endings) before committing.

- [ ] **Step 5: Commit**

```bash
git add apps/admin/src/features/training-data training/serving-lora-adapter.md
git commit -m "feat(admin): show, upload, download and remove an adapter's GGUF file"
```

---

### Final verification (after Task 6)

- [ ] Backend: `cd apps && uv run --project server pytest server/tests/training_data server/tests/core/test_storage.py -q`; `ruff check` and `ruff format --check` on every changed file; `cd apps/server && uv run alembic heads` shows a single head.
- [ ] Frontend: `cd apps/admin && pnpm exec vitest run` full suite, `pnpm exec tsc --noEmit`, `pnpm exec eslint src/features/training-data`.
- [ ] Notebook: round-trip check passes, 18 cells, existing notebook tests green.
- [ ] Manual (after merge, with the user): apply the migration to the shared database; in admin upload `sme-v7.gguf` and `sme-v8.gguf` with the Upload GGUF button, copy a download link and open it; run the next training and confirm the GGUF arrives by itself.

---

## Self-Review Notes

- **Spec coverage:** storage in R2 with local fallback (Task 1), metadata columns and token columns (Task 2), validation, token rules, replace, remove, link (Task 3), notebook-token upload, admin upload, download link, streaming fallback, delete, list field, `gguf_upload_url` in the zip response (Task 4), notebook step that never fails the run (Task 5), UI states and buttons and host doc (Task 6), additive migration and rollout (Tasks 2 and final).
- **Deviation from the spec text:** the spec said the app would reuse the existing storage layer as is. Reading it showed the document methods force keys under `documents/` and flatten directories, and presigned links cannot set a download file name. Task 1 therefore adds an additive artifact API instead of changing the document methods.
- **Consistency:** names used identically across tasks: `gguf_storage_key`, `gguf_sha256`, `gguf_size_bytes`, `gguf_uploaded_at`, `gguf_upload_token_hash`, `gguf_upload_expires_at`, `put_artifact`/`artifact_exists`/`delete_artifact`/`open_artifact`/`presign_artifact`, `store_gguf`, `remove_gguf`, `issue_gguf_upload_token`, `verify_gguf_upload_token`, `build_download_link`, `gguf_upload_url`, `AdapterGgufInfo`, `GgufDownloadLinkResponse`.
