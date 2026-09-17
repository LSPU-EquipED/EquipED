# DPO Colab Training Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a CID admin start a "training job" from the admin UI for one
agent, get a download URL and upload URL scoped to that job to paste into a
Colab notebook, and have the resulting trained LoRA adapter come back into
EquipED as a tracked, stored artifact.

**Architecture:** Two new backend tables (`dpo_training_jobs`,
`trained_adapters`) plus a small `training_data` module addition: job
creation freezes a DPO dataset snapshot (reusing the existing, untouched
`export_dpo_package()`) and mints two single-use, job-scoped opaque tokens;
a token-authenticated download endpoint serves the frozen snapshot with no
login required (the Colab runtime has none); a token-authenticated upload
endpoint accepts the trained adapter file and stores it on disk with a DB
record. A new admin-only sibling frontend feature (`training-data`) exposes
job creation, a job list, and an adapter list, following the existing
`agent-prompt` feature's per-agent `$agentId` route pattern.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), React + TanStack
Router/Query + `@equiped/api-client` (frontend), pytest + `TestClient`
(backend tests), Vitest + Testing Library (frontend tests).

**Spec:** `docs/superpowers/specs/2026-09-17-dpo-colab-training-handoff-design.md`

## Global Constraints

- Both tokens (download, upload) are single-use, stored hashed (SHA-256) at
  rest, never the raw value.
- Any token validation failure (expired, used, wrong job, malformed) returns
  HTTP 404, never 403 — do not confirm whether a guessed token/job exists.
- Do not modify `export_dpo_package()`, its projectors, or its capability
  registry. This plan only adds a transport/auth layer around it.
- Valid agent IDs are exactly `sme`, `coordinator`, `gad`, `itso` (matches
  `EvaluatorPermission` in `apps/server/modules/admin/schemas.py`).
- Backend: ruff-enforced (E, F, I, UP), line length 88, Python 3.12,
  `from __future__ import annotations` at the top of every new module.
- Frontend: TypeScript, no `any`, follow existing `preference-log` and
  `agent-prompt` feature conventions exactly (file layout, `requestJson`
  usage, TanStack Query hook shape).
- Run backend tests via `cd apps && uv run --project server pytest <path> -q`
  (never `uv run --project apps/server` from repo root — imports break).
- Run frontend tests via `pnpm --filter admin test` or the workspace-wide
  `pnpm test`.

---

## File Structure

```
apps/server/
  alembic/versions/
    20260917_0001_add_dpo_training_jobs_and_adapters.py   [new]
  modules/training_data/
    models.py       [new] DpoTrainingJob, TrainedAdapter ORM models
    exceptions.py   [new] TrainingDataError and subclasses
    tokens.py       [new] token generation/hashing/validation helpers
    paths.py        [new] ADAPTER_ROOT, adapter file path resolution
    jobs.py         [new] create_training_job, get_job_download_package, list_training_jobs
    adapters.py     [new] store_adapter_upload, list_trained_adapters
    schemas.py      [new] Pydantic request/response models
    router.py       [new] FastAPI router, mounted under /admin/training-data
    __init__.py     [modify] export new public names
  main.py            [modify] register training_data.router
  tests/training_data/
    test_tokens.py          [new]
    test_jobs.py             [new]
    test_adapters.py         [new]
    test_router.py           [new]

docs/colab/
  dpo_training_template.ipynb   [new] static notebook template

apps/admin/src/features/training-data/
  types.ts                          [new]
  api/trainingData.api.ts           [new]
  hooks/useTrainingJobs.ts          [new]
  hooks/useTrainedAdapters.ts       [new]
  hooks/useStartTrainingJob.ts      [new]
  components/TrainingJobsPanel.tsx  [new]
  components/AdapterListTable.tsx   [new]
  components/__tests__/TrainingJobsPanel.test.tsx  [new]
  pages/TrainingDataPage.tsx        [new]
apps/admin/src/app/
  router.tsx                        [modify]
  layout/navigation.utils.ts        [modify]
```

---

### Task 1: Migration + ORM models for `dpo_training_jobs` and `trained_adapters`

**Files:**
- Create: `apps/server/alembic/versions/20260917_0001_add_dpo_training_jobs_and_adapters.py`
- Create: `apps/server/modules/training_data/models.py`
- Test: `apps/server/tests/training_data/test_jobs.py` (model-shape smoke test only in this task; behavior tests come in Task 4+)

**Interfaces:**
- Produces: `DpoTrainingJob` ORM model with columns `job_id: uuid.UUID`
  (PK), `agent_id: str`, `status: str` (`pending`|`downloaded`|`completed`),
  `created_by: uuid.UUID` (FK `users.user_id`), `created_at: datetime`,
  `pairs_content: str`, `provenance_content: str`, `manifest_json: dict`,
  `download_token_hash: str`, `download_expires_at: datetime`,
  `download_used_at: datetime | None`, `upload_token_hash: str`,
  `upload_expires_at: datetime`, `upload_used_at: datetime | None`.
- Produces: `TrainedAdapter` ORM model with columns `adapter_id: uuid.UUID`
  (PK), `agent_id: str`, `job_id: uuid.UUID` (FK `dpo_training_jobs.job_id`),
  `version: int`, `file_path: str`, `file_sha256: str`, `size_bytes: int`,
  `created_at: datetime`.
- Later tasks import `DpoTrainingJob, TrainedAdapter` from
  `server.modules.training_data.models`.

- [ ] **Step 1: Write the model-shape test**

```python
"""apps/server/tests/training_data/test_jobs.py"""
from __future__ import annotations

import uuid

from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter


def test_dpo_training_job_round_trips(db_session, admin_user):
    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id="gad",
        status="pending",
        created_by=admin_user.user_id,
        pairs_content="",
        provenance_content="",
        manifest_json={},
        download_token_hash="a" * 64,
        download_expires_at=__import__("datetime").datetime.now(
            __import__("datetime").UTC
        ),
        upload_token_hash="b" * 64,
        upload_expires_at=__import__("datetime").datetime.now(
            __import__("datetime").UTC
        ),
    )
    db_session.add(job)
    db_session.commit()

    fetched = db_session.get(DpoTrainingJob, job.job_id)
    assert fetched is not None
    assert fetched.agent_id == "gad"
    assert fetched.status == "pending"


def test_trained_adapter_round_trips(db_session, admin_user):
    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id="gad",
        status="completed",
        created_by=admin_user.user_id,
        pairs_content="",
        provenance_content="",
        manifest_json={},
        download_token_hash="a" * 64,
        download_expires_at=__import__("datetime").datetime.now(
            __import__("datetime").UTC
        ),
        upload_token_hash="b" * 64,
        upload_expires_at=__import__("datetime").datetime.now(
            __import__("datetime").UTC
        ),
    )
    db_session.add(job)
    db_session.flush()

    adapter = TrainedAdapter(
        adapter_id=uuid.uuid4(),
        agent_id="gad",
        job_id=job.job_id,
        version=1,
        file_path="adapters/gad/x/adapter.zip",
        file_sha256="c" * 64,
        size_bytes=1024,
    )
    db_session.add(adapter)
    db_session.commit()

    fetched = db_session.get(TrainedAdapter, adapter.adapter_id)
    assert fetched is not None
    assert fetched.job_id == job.job_id
    assert fetched.version == 1
```

Note: the `__import__("datetime")` calls above are placeholders for a
proper top-of-file `from datetime import UTC, datetime` import — write the
test with that clean import instead:

```python
"""apps/server/tests/training_data/test_jobs.py"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter


def test_dpo_training_job_round_trips(db_session, admin_user):
    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id="gad",
        status="pending",
        created_by=admin_user.user_id,
        pairs_content="",
        provenance_content="",
        manifest_json={},
        download_token_hash="a" * 64,
        download_expires_at=datetime.now(UTC),
        upload_token_hash="b" * 64,
        upload_expires_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.commit()

    fetched = db_session.get(DpoTrainingJob, job.job_id)
    assert fetched is not None
    assert fetched.agent_id == "gad"
    assert fetched.status == "pending"


def test_trained_adapter_round_trips(db_session, admin_user):
    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id="gad",
        status="completed",
        created_by=admin_user.user_id,
        pairs_content="",
        provenance_content="",
        manifest_json={},
        download_token_hash="a" * 64,
        download_expires_at=datetime.now(UTC),
        upload_token_hash="b" * 64,
        upload_expires_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.flush()

    adapter = TrainedAdapter(
        adapter_id=uuid.uuid4(),
        agent_id="gad",
        job_id=job.job_id,
        version=1,
        file_path="adapters/gad/x/adapter.zip",
        file_sha256="c" * 64,
        size_bytes=1024,
    )
    db_session.add(adapter)
    db_session.commit()

    fetched = db_session.get(TrainedAdapter, adapter.adapter_id)
    assert fetched is not None
    assert fetched.job_id == job.job_id
    assert fetched.version == 1
```

You'll need an `admin_user` fixture — check
`apps/server/tests/admin/conftest.py` for the existing one; if
`apps/server/tests/training_data/conftest.py` doesn't already provide
`db_session`/`admin_user`, add a local `conftest.py` in
`apps/server/tests/training_data/` that imports/re-exports them from the
shared test fixtures (check `apps/server/tests/conftest.py` for the
project-wide `db_session` fixture first — it is very likely already
available to every test without a local conftest, matching how
`apps/server/tests/admin/test_preferences.py` uses `db_session` with no
local redefinition).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.training_data.models'`

- [ ] **Step 3: Write the ORM models**

```python
"""apps/server/modules/training_data/models.py"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from server.core.database import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column


class DpoTrainingJob(Base):
    """A frozen DPO dataset export paired with two job-scoped credentials.

    The dataset snapshot (pairs/provenance/manifest content) is captured at
    job-creation time so the download endpoint always returns exactly what
    was frozen then, even if new corrections land afterward.
    """

    __tablename__ = "dpo_training_jobs"
    __table_args__ = (
        CheckConstraint(
            sa.column("status").in_(["pending", "downloaded", "completed"]),
            name="ck_dpo_training_jobs_status",
        ),
        Index("idx_dpo_training_jobs_agent_id", "agent_id"),
        Index("idx_dpo_training_jobs_created_at", sa.text("created_at DESC")),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    pairs_content: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_content: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False)

    download_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    download_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    download_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    upload_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    upload_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TrainedAdapter(Base):
    """A trained LoRA adapter uploaded back from a Colab training run."""

    __tablename__ = "trained_adapters"
    __table_args__ = (
        Index("idx_trained_adapters_agent_id", "agent_id"),
        Index("idx_trained_adapters_job_id", "job_id"),
    )

    adapter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dpo_training_jobs.job_id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


__all__ = ["DpoTrainingJob", "TrainedAdapter"]
```

- [ ] **Step 4: Write the migration**

```python
"""apps/server/alembic/versions/20260917_0001_add_dpo_training_jobs_and_adapters.py"""
"""add dpo_training_jobs and trained_adapters tables

Revision ID: 20260917_0001
Revises: 20260915_0003
Create Date: 2026-09-17

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260917_0001"
down_revision = "20260915_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    if not _has_table("dpo_training_jobs"):
        op.create_table(
            "dpo_training_jobs",
            sa.Column("job_id", sa.Uuid(), primary_key=True),
            sa.Column("agent_id", sa.String(32), nullable=False, index=True),
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="pending"
            ),
            sa.Column(
                "created_by",
                sa.Uuid(),
                sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("pairs_content", sa.Text(), nullable=False),
            sa.Column("provenance_content", sa.Text(), nullable=False),
            sa.Column("manifest_json", sa.JSON(), nullable=False),
            sa.Column("download_token_hash", sa.String(64), nullable=False),
            sa.Column(
                "download_expires_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column(
                "download_used_at", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column("upload_token_hash", sa.String(64), nullable=False),
            sa.Column(
                "upload_expires_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column("upload_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('pending', 'downloaded', 'completed')",
                name="ck_dpo_training_jobs_status",
            ),
        )
        op.create_index(
            "idx_dpo_training_jobs_created_at",
            "dpo_training_jobs",
            [sa.text("created_at DESC")],
        )

    if not _has_table("trained_adapters"):
        op.create_table(
            "trained_adapters",
            sa.Column("adapter_id", sa.Uuid(), primary_key=True),
            sa.Column("agent_id", sa.String(32), nullable=False, index=True),
            sa.Column(
                "job_id",
                sa.Uuid(),
                sa.ForeignKey("dpo_training_jobs.job_id", ondelete="RESTRICT"),
                nullable=False,
                index=True,
            ),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("file_path", sa.String(512), nullable=False),
            sa.Column("file_sha256", sa.String(64), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    if _has_table("trained_adapters"):
        op.drop_table("trained_adapters")
    if _has_table("dpo_training_jobs"):
        op.drop_table("dpo_training_jobs")
```

Confirm `20260915_0003` is still the current head before setting
`down_revision`:

Run: `cd apps/server && uv run alembic heads`
Expected: exactly one head; if it is not `20260915_0003`, use whatever the
actual current head is instead.

- [ ] **Step 5: Apply the migration locally and run the tests**

Run: `cd apps/server && uv run alembic upgrade head`
Run: `cd apps && uv run --project server pytest server/tests/training_data/test_jobs.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add apps/server/alembic/versions/20260917_0001_add_dpo_training_jobs_and_adapters.py apps/server/modules/training_data/models.py apps/server/tests/training_data/test_jobs.py
git commit -m "feat(training-data): add dpo_training_jobs and trained_adapters tables"
```

---

### Task 2: Token utilities

**Files:**
- Create: `apps/server/modules/training_data/tokens.py`
- Test: `apps/server/tests/training_data/test_tokens.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `generate_raw_token() -> str`, `hash_token(raw_token: str) -> str`,
  `TOKEN_BYTES: int` constant. Later tasks (jobs.py, adapters.py) call
  `generate_raw_token()` when minting and `hash_token()` when validating.

- [ ] **Step 1: Write the failing test**

```python
"""apps/server/tests/training_data/test_tokens.py"""
from __future__ import annotations

from server.modules.training_data.tokens import generate_raw_token, hash_token


def test_generate_raw_token_is_url_safe_and_long_enough():
    token = generate_raw_token()
    assert len(token) >= 32
    assert all(c.isalnum() or c in "-_" for c in token)


def test_generate_raw_token_is_unique():
    tokens = {generate_raw_token() for _ in range(100)}
    assert len(tokens) == 100


def test_hash_token_is_deterministic_sha256_hex():
    raw = "fixed-value-for-hashing"
    first = hash_token(raw)
    second = hash_token(raw)
    assert first == second
    assert len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)


def test_hash_token_differs_for_different_input():
    assert hash_token("a") != hash_token("b")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_tokens.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.training_data.tokens'`

- [ ] **Step 3: Write the implementation**

```python
"""apps/server/modules/training_data/tokens.py"""
from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def generate_raw_token() -> str:
    """Generate a URL-safe opaque token. Never persisted in raw form."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(raw_token: str) -> str:
    """Hash a raw token for at-rest storage and comparison."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


__all__ = ["TOKEN_BYTES", "generate_raw_token", "hash_token"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_tokens.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/server/modules/training_data/tokens.py apps/server/tests/training_data/test_tokens.py
git commit -m "feat(training-data): add token generation and hashing utilities"
```

---

### Task 3: Exceptions module

**Files:**
- Create: `apps/server/modules/training_data/exceptions.py`
- Test: none (trivial exception classes; exercised indirectly by Task 4-6 tests)

**Interfaces:**
- Produces: `TrainingDataError(Exception)`, `InvalidAgentIdError(TrainingDataError)`,
  `TrainingJobNotFoundError(TrainingDataError)` (used for any token
  validation failure — expired, used, wrong job — the router maps this to
  404 regardless of which specific reason), `AdapterUploadError(TrainingDataError)`
  (oversized file, disallowed extension).

- [ ] **Step 1: Write the exceptions**

```python
"""apps/server/modules/training_data/exceptions.py"""
from __future__ import annotations


class TrainingDataError(Exception):
    """Base exception for the training_data module."""


class InvalidAgentIdError(TrainingDataError):
    """Raised when agent_id is not one of the four known agents."""


class TrainingJobNotFoundError(TrainingDataError):
    """Raised for any token validation failure: missing, expired, used,
    or scoped to a different job. Deliberately undifferentiated so callers
    cannot use error variants to probe for valid tokens/job IDs."""


class AdapterUploadError(TrainingDataError):
    """Raised when an uploaded adapter file fails size or extension checks."""


__all__ = [
    "TrainingDataError",
    "InvalidAgentIdError",
    "TrainingJobNotFoundError",
    "AdapterUploadError",
]
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd apps && uv run --project server python -c "from server.modules.training_data.exceptions import TrainingDataError, InvalidAgentIdError, TrainingJobNotFoundError, AdapterUploadError"`
Expected: no output, exit code 0

- [ ] **Step 3: Commit**

```bash
git add apps/server/modules/training_data/exceptions.py
git commit -m "feat(training-data): add module exception types"
```

---

### Task 4: Job creation service (`create_training_job`)

**Files:**
- Create: `apps/server/modules/training_data/jobs.py`
- Modify: `apps/server/tests/training_data/test_jobs.py` (add creation tests)

**Interfaces:**
- Consumes: `DpoTrainingJob` from `training_data.models` (Task 1);
  `generate_raw_token, hash_token` from `training_data.tokens` (Task 2);
  `InvalidAgentIdError` from `training_data.exceptions` (Task 3);
  `export_dpo_package` from `training_data.exporter` (existing, untouched).
- Produces: `VALID_AGENT_IDS: frozenset[str]`,
  `create_training_job(session: Session, agent_id: str, created_by: uuid.UUID) -> TrainingJobCreated`
  where `TrainingJobCreated` is a frozen dataclass with fields
  `job: DpoTrainingJob`, `raw_download_token: str`, `raw_upload_token: str`.
  Later tasks (router.py) call this and use `.job.job_id`,
  `.raw_download_token`, `.raw_upload_token`.

- [ ] **Step 1: Add the failing tests**

Append to `apps/server/tests/training_data/test_jobs.py`:

```python
import pytest
from server.modules.training_data.exceptions import InvalidAgentIdError
from server.modules.training_data.jobs import create_training_job
from server.modules.training_data.models import DpoTrainingJob
from server.modules.training_data.tokens import hash_token
from server.tests.evaluations.conftest import _add_document
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentGeneration
import uuid as uuid_module


def _make_gad_generation(db_session, owner_id, agent_id="gad"):
    document_id = _add_document(db_session, owner_id=owner_id, source_type="slm")
    job = EvaluationJob(evaluation_id=uuid_module.uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    generation = AgentGeneration(
        generation_id=uuid_module.uuid4(),
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_id=agent_id,
        unit_key="gad-01",
        criterion_ids=["GAD-01"],
        prompt_text="prompt",
        response_text='{"gad-01": {"score": 2, "reasoning": "r"}}',
        response_json={"gad-01": {"score": 2, "reasoning": "r"}},
        response_contract_key="gad_scores.v1",
        response_contract_version=1,
        model_name="test-model",
        envelope_status="ok",
        prompt_sha256="p" * 64,
        response_sha256="r" * 64,
    )
    db_session.add(generation)
    db_session.commit()
    return job.evaluation_id


def test_create_training_job_rejects_unknown_agent(db_session, admin_user):
    with pytest.raises(InvalidAgentIdError):
        create_training_job(db_session, "not-a-real-agent", admin_user.user_id)


def test_create_training_job_freezes_dataset_and_mints_tokens(
    db_session, admin_user
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)

    result = create_training_job(db_session, "gad", admin_user.user_id)

    assert result.job.agent_id == "gad"
    assert result.job.status == "pending"
    assert result.job.created_by == admin_user.user_id
    assert isinstance(result.job.manifest_json, dict)
    assert result.job.download_token_hash == hash_token(result.raw_download_token)
    assert result.job.upload_token_hash == hash_token(result.raw_upload_token)
    assert result.raw_download_token != result.raw_upload_token

    fetched = db_session.get(DpoTrainingJob, result.job.job_id)
    assert fetched is not None
    assert fetched.status == "pending"
```

Check the exact required/optional fields on `AgentGeneration` and
`EvaluationJob` before running this — read
`apps/server/modules/synthesis/models.py` and
`apps/server/modules/evaluations/models.py`. If `AgentGeneration` requires
additional non-nullable fields not listed above (e.g. `form_snapshot_id`,
`agent_result_id`), add them using the same pattern already used in
`apps/server/tests/training_data/test_projectors.py` or
`apps/server/tests/training_data/test_exporter.py` (both already read into
context earlier in this session — check for an existing generation-building
test helper there and reuse it instead of duplicating one, if one exists).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.training_data.jobs'`

- [ ] **Step 3: Write the implementation**

```python
"""apps/server/modules/training_data/jobs.py"""
from __future__ import annotations

import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from server.modules.training_data.exceptions import InvalidAgentIdError
from server.modules.training_data.exporter import export_dpo_package
from server.modules.training_data.models import DpoTrainingJob
from server.modules.training_data.tokens import generate_raw_token, hash_token
from sqlalchemy.orm import Session

VALID_AGENT_IDS: frozenset[str] = frozenset({"sme", "coordinator", "gad", "itso"})

_DOWNLOAD_TOKEN_LIFETIME = timedelta(hours=24)
_UPLOAD_TOKEN_LIFETIME = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class TrainingJobCreated:
    job: DpoTrainingJob
    raw_download_token: str
    raw_upload_token: str


def _freeze_dataset(session: Session, agent_id: str) -> tuple[str, str, dict]:
    """Run export_dpo_package() to a scratch dir, read its output back as
    content, then delete the scratch dir. export_dpo_package() itself is
    not modified -- this only reads what it already writes."""
    scratch_root = tempfile.mkdtemp(prefix=".dpo_job_freeze_")
    scratch_dir = Path(scratch_root) / "package"
    try:
        export_dpo_package(session, agent_id, scratch_dir)
        pairs_content = (scratch_dir / "pairs.jsonl").read_text(encoding="utf-8")
        provenance_content = (scratch_dir / "provenance.jsonl").read_text(
            encoding="utf-8"
        )
        manifest_json = (scratch_dir / "manifest.json").read_text(encoding="utf-8")
        import json

        return pairs_content, provenance_content, json.loads(manifest_json)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)


def create_training_job(
    session: Session, agent_id: str, created_by: uuid.UUID
) -> TrainingJobCreated:
    """Create a training job: freeze the current DPO dataset for agent_id
    and mint a single-use download token plus a single-use upload token,
    both scoped to the new job."""
    if agent_id not in VALID_AGENT_IDS:
        raise InvalidAgentIdError(f"unknown agent_id: {agent_id!r}")

    pairs_content, provenance_content, manifest_json = _freeze_dataset(
        session, agent_id
    )

    raw_download_token = generate_raw_token()
    raw_upload_token = generate_raw_token()
    now = datetime.now(UTC)

    job = DpoTrainingJob(
        job_id=uuid.uuid4(),
        agent_id=agent_id,
        status="pending",
        created_by=created_by,
        pairs_content=pairs_content,
        provenance_content=provenance_content,
        manifest_json=manifest_json,
        download_token_hash=hash_token(raw_download_token),
        download_expires_at=now + _DOWNLOAD_TOKEN_LIFETIME,
        upload_token_hash=hash_token(raw_upload_token),
        upload_expires_at=now + _UPLOAD_TOKEN_LIFETIME,
    )
    session.add(job)
    session.commit()

    return TrainingJobCreated(
        job=job,
        raw_download_token=raw_download_token,
        raw_upload_token=raw_upload_token,
    )


__all__ = ["VALID_AGENT_IDS", "TrainingJobCreated", "create_training_job"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_jobs.py -v`
Expected: PASS (all tests, including Task 1's)

- [ ] **Step 5: Commit**

```bash
git add apps/server/modules/training_data/jobs.py apps/server/tests/training_data/test_jobs.py
git commit -m "feat(training-data): add create_training_job with dataset freezing"
```

---

### Task 5: Download package retrieval (`get_job_download_package`)

**Files:**
- Modify: `apps/server/modules/training_data/jobs.py` (add function)
- Modify: `apps/server/tests/training_data/test_jobs.py` (add tests)

**Interfaces:**
- Consumes: `DpoTrainingJob` (Task 1), `hash_token` (Task 2),
  `TrainingJobNotFoundError` (Task 3).
- Produces: `get_job_download_package(session: Session, job_id: uuid.UUID, raw_token: str) -> bytes`
  — returns zip file bytes built in-memory from the job's frozen content, or
  raises `TrainingJobNotFoundError` for any invalid-token condition. Marks
  the download token used and advances `status` to `"downloaded"` as a side
  effect on success. Later tasks (router.py) call this directly.

- [ ] **Step 1: Add the failing tests**

Append to `apps/server/tests/training_data/test_jobs.py`:

```python
import io
import zipfile

from server.modules.training_data.exceptions import TrainingJobNotFoundError
from server.modules.training_data.jobs import get_job_download_package


def test_get_job_download_package_returns_zip_with_expected_files(
    db_session, admin_user
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    zip_bytes = get_job_download_package(
        db_session, result.job.job_id, result.raw_download_token
    )

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        assert names == {"pairs.jsonl", "provenance.jsonl", "manifest.json"}

    refreshed = db_session.get(DpoTrainingJob, result.job.job_id)
    assert refreshed.status == "downloaded"
    assert refreshed.download_used_at is not None


def test_get_job_download_package_rejects_reuse(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    get_job_download_package(db_session, result.job.job_id, result.raw_download_token)

    with pytest.raises(TrainingJobNotFoundError):
        get_job_download_package(
            db_session, result.job.job_id, result.raw_download_token
        )


def test_get_job_download_package_rejects_wrong_token(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    with pytest.raises(TrainingJobNotFoundError):
        get_job_download_package(db_session, result.job.job_id, "wrong-token")


def test_get_job_download_package_rejects_unknown_job(db_session, admin_user):
    with pytest.raises(TrainingJobNotFoundError):
        get_job_download_package(db_session, uuid_module.uuid4(), "wrong-token")


def test_get_job_download_package_rejects_expired_token(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    from datetime import UTC, datetime, timedelta

    job = db_session.get(DpoTrainingJob, result.job.job_id)
    job.download_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(TrainingJobNotFoundError):
        get_job_download_package(
            db_session, result.job.job_id, result.raw_download_token
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_jobs.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_job_download_package'`

- [ ] **Step 3: Add the implementation**

Add to `apps/server/modules/training_data/jobs.py`:

```python
import io
import zipfile

from server.modules.training_data.exceptions import TrainingJobNotFoundError


def get_job_download_package(
    session: Session, job_id: uuid.UUID, raw_token: str
) -> bytes:
    """Validate the download token and return the frozen package as zip
    bytes. Raises TrainingJobNotFoundError for any invalid-token condition
    -- callers must map this to HTTP 404, never 403."""
    job = session.get(DpoTrainingJob, job_id)
    if job is None:
        raise TrainingJobNotFoundError("job not found")

    now = datetime.now(UTC)
    if (
        job.download_used_at is not None
        or job.download_expires_at < now
        or hash_token(raw_token) != job.download_token_hash
    ):
        raise TrainingJobNotFoundError("invalid or expired download token")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pairs.jsonl", job.pairs_content)
        zf.writestr("provenance.jsonl", job.provenance_content)
        import json

        zf.writestr("manifest.json", json.dumps(job.manifest_json, indent=2))

    job.download_used_at = now
    job.status = "downloaded"
    session.commit()

    return buffer.getvalue()
```

Update `__all__` in the same file to also export `get_job_download_package`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_jobs.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add apps/server/modules/training_data/jobs.py apps/server/tests/training_data/test_jobs.py
git commit -m "feat(training-data): add token-validated dataset download"
```

---

### Task 6: Adapter storage paths + upload service

**Files:**
- Create: `apps/server/modules/training_data/paths.py`
- Create: `apps/server/modules/training_data/adapters.py`
- Create: `apps/server/tests/training_data/test_adapters.py`

**Interfaces:**
- Consumes: `DpoTrainingJob, TrainedAdapter` (Task 1), `hash_token` (Task 2),
  `TrainingJobNotFoundError, AdapterUploadError` (Task 3).
- Produces: `ADAPTER_ROOT: Path` (paths.py);
  `store_adapter_upload(session: Session, job_id: uuid.UUID, raw_token: str, filename: str, content: bytes) -> TrainedAdapter`
  (adapters.py) — validates the upload token the same way Task 5 validates
  the download token, validates size/extension, writes the file under
  `ADAPTER_ROOT`, writes a `TrainedAdapter` row, marks the upload token
  used and job `status = "completed"`. Later tasks (router.py) call this.

- [ ] **Step 1: Write `paths.py`**

```python
"""apps/server/modules/training_data/paths.py"""
from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
ADAPTER_ROOT = _PROJECT_ROOT / "adapters"

MAX_ADAPTER_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB -- comfortably fits a
# LoRA adapter (typically tens to low hundreds of MB), not full model weights.
ALLOWED_ADAPTER_EXTENSIONS = frozenset({".zip"})


__all__ = ["ADAPTER_ROOT", "MAX_ADAPTER_UPLOAD_BYTES", "ALLOWED_ADAPTER_EXTENSIONS"]
```

- [ ] **Step 2: Write the failing tests**

```python
"""apps/server/tests/training_data/test_adapters.py"""
from __future__ import annotations

import uuid as uuid_module

import pytest
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentGeneration
from server.modules.training_data.adapters import list_trained_adapters, store_adapter_upload
from server.modules.training_data.exceptions import (
    AdapterUploadError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.jobs import create_training_job, get_job_download_package
from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter
from server.modules.training_data.paths import ADAPTER_ROOT, MAX_ADAPTER_UPLOAD_BYTES
from server.tests.evaluations.conftest import _add_document


def _make_gad_generation(db_session, owner_id, agent_id="gad"):
    document_id = _add_document(db_session, owner_id=owner_id, source_type="slm")
    job = EvaluationJob(evaluation_id=uuid_module.uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    generation = AgentGeneration(
        generation_id=uuid_module.uuid4(),
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_id=agent_id,
        unit_key="gad-01",
        criterion_ids=["GAD-01"],
        prompt_text="prompt",
        response_text='{"gad-01": {"score": 2, "reasoning": "r"}}',
        response_json={"gad-01": {"score": 2, "reasoning": "r"}},
        response_contract_key="gad_scores.v1",
        response_contract_version=1,
        model_name="test-model",
        envelope_status="ok",
        prompt_sha256="p" * 64,
        response_sha256="r" * 64,
    )
    db_session.add(generation)
    db_session.commit()
    return job.evaluation_id


def test_store_adapter_upload_writes_file_and_row(db_session, admin_user, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path
    )
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    adapter = store_adapter_upload(
        db_session,
        result.job.job_id,
        result.raw_upload_token,
        filename="adapter.zip",
        content=b"fake-adapter-bytes",
    )

    assert adapter.agent_id == "gad"
    assert adapter.job_id == result.job.job_id
    assert adapter.version == 1
    assert adapter.size_bytes == len(b"fake-adapter-bytes")
    stored_path = tmp_path.parent.joinpath(adapter.file_path) if not adapter.file_path.startswith(str(tmp_path)) else __import__("pathlib").Path(adapter.file_path)

    refreshed_job = db_session.get(DpoTrainingJob, result.job.job_id)
    assert refreshed_job.status == "completed"
    assert refreshed_job.upload_used_at is not None


def test_store_adapter_upload_rejects_reuse(db_session, admin_user, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path
    )
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    store_adapter_upload(
        db_session,
        result.job.job_id,
        result.raw_upload_token,
        filename="adapter.zip",
        content=b"one",
    )

    with pytest.raises(TrainingJobNotFoundError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.zip",
            content=b"two",
        )


def test_store_adapter_upload_rejects_wrong_token(db_session, admin_user, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path
    )
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    with pytest.raises(TrainingJobNotFoundError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            "wrong-token",
            filename="adapter.zip",
            content=b"one",
        )


def test_store_adapter_upload_rejects_bad_extension(db_session, admin_user, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path
    )
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    with pytest.raises(AdapterUploadError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.exe",
            content=b"one",
        )


def test_store_adapter_upload_rejects_oversized_file(db_session, admin_user, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path
    )
    monkeypatch.setattr(
        "server.modules.training_data.adapters.MAX_ADAPTER_UPLOAD_BYTES", 10
    )
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    result = create_training_job(db_session, "gad", admin_user.user_id)

    with pytest.raises(AdapterUploadError):
        store_adapter_upload(
            db_session,
            result.job.job_id,
            result.raw_upload_token,
            filename="adapter.zip",
            content=b"x" * 11,
        )


def test_list_trained_adapters_returns_newest_first(db_session, admin_user, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path
    )
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    first = create_training_job(db_session, "gad", admin_user.user_id)
    store_adapter_upload(
        db_session, first.job.job_id, first.raw_upload_token,
        filename="a.zip", content=b"a",
    )

    second = create_training_job(db_session, "gad", admin_user.user_id)
    store_adapter_upload(
        db_session, second.job.job_id, second.raw_upload_token,
        filename="b.zip", content=b"b",
    )

    adapters = list_trained_adapters(db_session, "gad")
    assert [a.version for a in adapters] == [2, 1]
```

Remove the unused `stored_path` line from the first test (it was scratch
reasoning, not a real assertion) before running — clean it up to just the
assertions shown for `adapter` and `refreshed_job`.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_adapters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.training_data.adapters'`

- [ ] **Step 4: Write the implementation**

```python
"""apps/server/modules/training_data/adapters.py"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from server.modules.training_data.exceptions import (
    AdapterUploadError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.models import DpoTrainingJob, TrainedAdapter
from server.modules.training_data.paths import (
    ADAPTER_ROOT,
    ALLOWED_ADAPTER_EXTENSIONS,
    MAX_ADAPTER_UPLOAD_BYTES,
)
from server.modules.training_data.tokens import hash_token
from sqlalchemy import func
from sqlalchemy.orm import Session


def _next_version(session: Session, agent_id: str) -> int:
    current_max = (
        session.query(func.max(TrainedAdapter.version))
        .filter(TrainedAdapter.agent_id == agent_id)
        .scalar()
    )
    return (current_max or 0) + 1


def store_adapter_upload(
    session: Session,
    job_id: uuid.UUID,
    raw_token: str,
    *,
    filename: str,
    content: bytes,
) -> TrainedAdapter:
    """Validate the upload token, persist the adapter file, and record a
    TrainedAdapter row. Raises TrainingJobNotFoundError for any
    invalid-token condition (callers map this to HTTP 404) or
    AdapterUploadError for a valid token with a disallowed file."""
    job = session.get(DpoTrainingJob, job_id)
    if job is None:
        raise TrainingJobNotFoundError("job not found")

    now = datetime.now(UTC)
    if (
        job.upload_used_at is not None
        or job.upload_expires_at < now
        or hash_token(raw_token) != job.upload_token_hash
    ):
        raise TrainingJobNotFoundError("invalid or expired upload token")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_ADAPTER_EXTENSIONS:
        raise AdapterUploadError(f"disallowed file extension: {extension!r}")
    if len(content) > MAX_ADAPTER_UPLOAD_BYTES:
        raise AdapterUploadError(
            f"file exceeds max size of {MAX_ADAPTER_UPLOAD_BYTES} bytes"
        )

    version = _next_version(session, job.agent_id)
    adapter_id = uuid.uuid4()
    target_dir = ADAPTER_ROOT / job.agent_id / str(adapter_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"adapter{extension}"
    target_path.write_bytes(content)

    adapter = TrainedAdapter(
        adapter_id=adapter_id,
        agent_id=job.agent_id,
        job_id=job.job_id,
        version=version,
        file_path=str(target_path),
        file_sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )
    session.add(adapter)

    job.upload_used_at = now
    job.status = "completed"

    session.commit()
    return adapter


def list_trained_adapters(session: Session, agent_id: str) -> list[TrainedAdapter]:
    return (
        session.query(TrainedAdapter)
        .filter(TrainedAdapter.agent_id == agent_id)
        .order_by(TrainedAdapter.version.desc())
        .all()
    )


__all__ = ["store_adapter_upload", "list_trained_adapters"]
```

Note the test monkeypatches `server.modules.training_data.adapters.ADAPTER_ROOT`
(not `training_data.paths.ADAPTER_ROOT`) — this only works if `adapters.py`
imports the name into its own module namespace via
`from server.modules.training_data.paths import ADAPTER_ROOT`, exactly as
written above, since `monkeypatch.setattr` rebinds the name in the
`adapters` module, not in `paths`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_adapters.py -v`
Expected: PASS (all tests)

- [ ] **Step 6: Add `adapters/` to `.gitignore`**

Check `apps/server/.gitignore` or the repo-root `.gitignore` for how
`uploads/` is excluded (search for it), and add the same pattern for the
new `adapters/` runtime directory at the repo root.

- [ ] **Step 7: Commit**

```bash
git add apps/server/modules/training_data/paths.py apps/server/modules/training_data/adapters.py apps/server/tests/training_data/test_adapters.py .gitignore
git commit -m "feat(training-data): add adapter upload storage and listing"
```

---

### Task 7: `list_training_jobs` + Pydantic schemas

**Files:**
- Modify: `apps/server/modules/training_data/jobs.py` (add `list_training_jobs`)
- Create: `apps/server/modules/training_data/schemas.py`
- Modify: `apps/server/tests/training_data/test_jobs.py` (add list test)

**Interfaces:**
- Consumes: `DpoTrainingJob` (Task 1).
- Produces: `list_training_jobs(session: Session, agent_id: str) -> list[DpoTrainingJob]`
  (newest first); Pydantic schemas `TrainingJobCreateResponse`,
  `TrainingJobListItem`, `TrainingJobListResponse`, `TrainedAdapterResponse`,
  `TrainedAdapterListResponse` for the router (Task 8) to use as
  `response_model`s.

- [ ] **Step 1: Add the failing test**

Append to `apps/server/tests/training_data/test_jobs.py`:

```python
from server.modules.training_data.jobs import list_training_jobs


def test_list_training_jobs_returns_newest_first(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    first = create_training_job(db_session, "gad", admin_user.user_id)
    second = create_training_job(db_session, "gad", admin_user.user_id)

    jobs = list_training_jobs(db_session, "gad")

    assert [j.job_id for j in jobs] == [second.job.job_id, first.job.job_id]


def test_list_training_jobs_filters_by_agent(db_session, admin_user):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    create_training_job(db_session, "gad", admin_user.user_id)

    itso_jobs = list_training_jobs(db_session, "itso")
    assert itso_jobs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_jobs.py -v`
Expected: FAIL with `ImportError: cannot import name 'list_training_jobs'`

- [ ] **Step 3: Add `list_training_jobs` to `jobs.py`**

Add to `apps/server/modules/training_data/jobs.py`:

```python
def list_training_jobs(session: Session, agent_id: str) -> list[DpoTrainingJob]:
    return (
        session.query(DpoTrainingJob)
        .filter(DpoTrainingJob.agent_id == agent_id)
        .order_by(DpoTrainingJob.created_at.desc())
        .all()
    )
```

Update `__all__` in `jobs.py` to also export `list_training_jobs`.

- [ ] **Step 4: Write `schemas.py`**

```python
"""apps/server/modules/training_data/schemas.py"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

AgentId = Literal["sme", "coordinator", "gad", "itso"]


class TrainingJobCreateResponse(BaseModel):
    job_id: uuid.UUID
    agent_id: str
    status: str
    download_url: str
    upload_url: str
    download_expires_at: datetime
    upload_expires_at: datetime
    created_at: datetime


class TrainingJobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    agent_id: str
    status: str
    created_at: datetime


class TrainingJobListResponse(BaseModel):
    agent_id: str
    jobs: list[TrainingJobListItem]


class TrainedAdapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    adapter_id: uuid.UUID
    agent_id: str
    job_id: uuid.UUID
    version: int
    file_sha256: str
    size_bytes: int
    created_at: datetime


class TrainedAdapterListResponse(BaseModel):
    agent_id: str
    adapters: list[TrainedAdapterResponse]


__all__ = [
    "AgentId",
    "TrainingJobCreateResponse",
    "TrainingJobListItem",
    "TrainingJobListResponse",
    "TrainedAdapterResponse",
    "TrainedAdapterListResponse",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_jobs.py -v`
Expected: PASS (all tests)

- [ ] **Step 6: Verify schemas import cleanly**

Run: `cd apps && uv run --project server python -c "from server.modules.training_data.schemas import TrainingJobCreateResponse, TrainingJobListResponse, TrainedAdapterListResponse"`
Expected: no output, exit code 0

- [ ] **Step 7: Commit**

```bash
git add apps/server/modules/training_data/jobs.py apps/server/modules/training_data/schemas.py apps/server/tests/training_data/test_jobs.py
git commit -m "feat(training-data): add job listing and admin response schemas"
```

---

### Task 8: Router + main.py registration

**Files:**
- Create: `apps/server/modules/training_data/router.py`
- Modify: `apps/server/main.py`
- Modify: `apps/server/modules/training_data/__init__.py`
- Create: `apps/server/tests/training_data/test_router.py`
- Create: `apps/server/tests/training_data/__init__.py` (if not already present from Task 1)

**Interfaces:**
- Consumes: everything from Tasks 1-7: `create_training_job,
  get_job_download_package, list_training_jobs` (jobs.py);
  `store_adapter_upload, list_trained_adapters` (adapters.py); all schemas
  (schemas.py); `InvalidAgentIdError, TrainingJobNotFoundError,
  AdapterUploadError` (exceptions.py); `require_admin` (existing,
  `server.modules.auth.dependencies`).
- Produces: `router: APIRouter` mounted at `/admin/training-data`, wired
  into `MODULE_ROUTER_PATHS` in `main.py` so it's picked up automatically.

- [ ] **Step 1: Ensure the test package exists**

If `apps/server/tests/training_data/__init__.py` doesn't already exist from
an earlier task's test run, create it empty (matches the convention used by
every other `apps/server/tests/<module>/__init__.py`).

- [ ] **Step 2: Write the failing router tests**

```python
"""apps/server/tests/training_data/test_router.py"""
from __future__ import annotations

import uuid as uuid_module

from fastapi.testclient import TestClient
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentGeneration
from server.tests.admin.conftest import _auth
from server.tests.evaluations.conftest import _add_document


def _make_gad_generation(db_session, owner_id, agent_id="gad"):
    document_id = _add_document(db_session, owner_id=owner_id, source_type="slm")
    job = EvaluationJob(evaluation_id=uuid_module.uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    generation = AgentGeneration(
        generation_id=uuid_module.uuid4(),
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_id=agent_id,
        unit_key="gad-01",
        criterion_ids=["GAD-01"],
        prompt_text="prompt",
        response_text='{"gad-01": {"score": 2, "reasoning": "r"}}',
        response_json={"gad-01": {"score": 2, "reasoning": "r"}},
        response_contract_key="gad_scores.v1",
        response_contract_version=1,
        model_name="test-model",
        envelope_status="ok",
        prompt_sha256="p" * 64,
        response_sha256="r" * 64,
    )
    db_session.add(generation)
    db_session.commit()


def test_start_job_requires_admin(client: TestClient, auth_cookies_faculty):
    _auth(client, auth_cookies_faculty)
    response = client.post("/api/v1/admin/training-data/gad/jobs")
    assert response.status_code == 403


def test_start_job_rejects_unknown_agent(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _auth(client, auth_cookies_admin)
    response = client.post("/api/v1/admin/training-data/not-real/jobs")
    assert response.status_code == 400


def test_start_job_returns_download_and_upload_urls(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)

    response = client.post("/api/v1/admin/training-data/gad/jobs")

    assert response.status_code == 201
    body = response.json()
    assert body["agent_id"] == "gad"
    assert body["status"] == "pending"
    assert "download_url" in body and "token=" in body["download_url"]
    assert "upload_url" in body and "token=" in body["upload_url"]


def test_download_endpoint_requires_no_login_but_valid_token(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)
    create_response = client.post("/api/v1/admin/training-data/gad/jobs")
    body = create_response.json()

    client.cookies.clear()  # simulate the anonymous Colab runtime
    download_path = body["download_url"].split("/api/v1", 1)[1]
    download_response = client.get(f"/api/v1{download_path}")

    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/zip"


def test_download_endpoint_rejects_bad_token(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)
    create_response = client.post("/api/v1/admin/training-data/gad/jobs")
    job_id = create_response.json()["job_id"]

    client.cookies.clear()
    response = client.get(
        f"/api/v1/admin/training-data/jobs/{job_id}/download?token=wrong"
    )
    assert response.status_code == 404


def test_upload_endpoint_stores_adapter_and_list_reflects_it(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)
    create_response = client.post("/api/v1/admin/training-data/gad/jobs")
    body = create_response.json()
    job_id = body["job_id"]
    upload_path = body["upload_url"].split("/api/v1", 1)[1]

    client.cookies.clear()
    upload_response = client.post(
        f"/api/v1{upload_path}",
        files={"file": ("adapter.zip", b"fake-bytes", "application/zip")},
    )
    assert upload_response.status_code == 201

    _auth(client, auth_cookies_admin)
    list_response = client.get("/api/v1/admin/training-data/gad/adapters")
    assert list_response.status_code == 200
    adapters = list_response.json()["adapters"]
    assert len(adapters) == 1
    assert adapters[0]["job_id"] == job_id


def test_jobs_list_requires_admin(client: TestClient, auth_cookies_faculty):
    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/training-data/gad/jobs")
    assert response.status_code == 403
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps && uv run --project server pytest server/tests/training_data/test_router.py -v`
Expected: FAIL — connection/404 errors since the router doesn't exist yet
and isn't registered.

- [ ] **Step 4: Write the router**

```python
"""apps/server/modules/training_data/router.py"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin
from server.modules.auth.service import AuthenticatedUser
from server.modules.training_data.adapters import (
    list_trained_adapters,
    store_adapter_upload,
)
from server.modules.training_data.exceptions import (
    AdapterUploadError,
    InvalidAgentIdError,
    TrainingJobNotFoundError,
)
from server.modules.training_data.jobs import (
    create_training_job,
    get_job_download_package,
    list_training_jobs,
)
from server.modules.training_data.schemas import (
    TrainedAdapterListResponse,
    TrainedAdapterResponse,
    TrainingJobCreateResponse,
    TrainingJobListItem,
    TrainingJobListResponse,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/training-data", tags=["training-data"])


def _build_url(request: Request, path: str) -> str:
    base = str(request.base_url).rstrip("/")
    api_prefix = request.scope.get("root_path", "") or "/api/v1"
    return f"{base}{api_prefix}{path}"


@router.post(
    "/{agent_id}/jobs",
    response_model=TrainingJobCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_training_job(
    agent_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainingJobCreateResponse:
    try:
        result = create_training_job(db, agent_id, current_user.id)
    except InvalidAgentIdError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    download_path = f"/admin/training-data/jobs/{result.job.job_id}/download?token={result.raw_download_token}"
    upload_path = f"/admin/training-data/jobs/{result.job.job_id}/adapter?token={result.raw_upload_token}"

    return TrainingJobCreateResponse(
        job_id=result.job.job_id,
        agent_id=result.job.agent_id,
        status=result.job.status,
        download_url=_build_url(request, download_path),
        upload_url=_build_url(request, upload_path),
        download_expires_at=result.job.download_expires_at,
        upload_expires_at=result.job.upload_expires_at,
        created_at=result.job.created_at,
    )


@router.get("/jobs/{job_id}/download")
def download_training_job_package(
    job_id: uuid.UUID,
    token: str = Query(...),
    db: Session = Depends(get_db_session),
) -> Response:
    try:
        zip_bytes = get_job_download_package(db, job_id, token)
    except TrainingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc

    return Response(content=zip_bytes, media_type="application/zip")


@router.post(
    "/jobs/{job_id}/adapter",
    response_model=TrainedAdapterResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_trained_adapter(
    job_id: uuid.UUID,
    token: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterResponse:
    content = file.file.read()
    try:
        adapter = store_adapter_upload(
            db, job_id, token, filename=file.filename or "", content=content
        )
    except TrainingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc
    except AdapterUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return TrainedAdapterResponse.model_validate(adapter)


@router.get("/{agent_id}/jobs", response_model=TrainingJobListResponse)
def get_training_jobs(
    agent_id: str,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainingJobListResponse:
    jobs = list_training_jobs(db, agent_id)
    return TrainingJobListResponse(
        agent_id=agent_id,
        jobs=[TrainingJobListItem.model_validate(j) for j in jobs],
    )


@router.get("/{agent_id}/adapters", response_model=TrainedAdapterListResponse)
def get_trained_adapters(
    agent_id: str,
    _current_user: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> TrainedAdapterListResponse:
    adapters = list_trained_adapters(db, agent_id)
    return TrainedAdapterListResponse(
        agent_id=agent_id,
        adapters=[TrainedAdapterResponse.model_validate(a) for a in adapters],
    )


__all__ = ["router"]
```

Before trusting `request.scope.get("root_path", "")`, check how
`settings.api_prefix` is used elsewhere (e.g. in `main.py`'s
`APIRouter(prefix=settings.api_prefix)`) — if `root_path` is not reliably
`/api/v1` in the test client, replace `_build_url`'s `api_prefix` line with
an explicit import: `from server.core.config import get_settings` and
`get_settings().api_prefix`, matching how other modules already obtain it.
Prefer the explicit settings-based version if there's any doubt — verify
against the router test in Step 3 rather than assuming.

- [ ] **Step 5: Register the router in `main.py`**

In `apps/server/main.py`, add `"server.modules.training_data.router",` to
the `MODULE_ROUTER_PATHS` tuple (alongside the existing entries like
`"server.modules.rubrics.router"`).

- [ ] **Step 6: Export new names from `training_data/__init__.py`**

Add to the existing imports/`__all__` in
`apps/server/modules/training_data/__init__.py`:

```python
from .jobs import create_training_job, get_job_download_package, list_training_jobs
from .adapters import list_trained_adapters, store_adapter_upload
```

and add `"create_training_job", "get_job_download_package",
"list_training_jobs", "list_trained_adapters", "store_adapter_upload"` to
`__all__`.

- [ ] **Step 7: Run test to verify it passes**

Run: `cd apps && uv run --project server pytest server/tests/training_data/ -v`
Expected: PASS (all tests across the whole training_data test package)

- [ ] **Step 8: Run the full training_data + admin test suites to check for regressions**

Run: `cd apps && uv run --project server pytest server/tests/training_data/ server/tests/admin/ -q`
Expected: all pass, no new failures

- [ ] **Step 9: Commit**

```bash
git add apps/server/modules/training_data/router.py apps/server/modules/training_data/__init__.py apps/server/main.py apps/server/tests/training_data/test_router.py apps/server/tests/training_data/__init__.py
git commit -m "feat(training-data): add admin training-job router and wire into app"
```

---

### Task 9: Colab notebook template

**Files:**
- Create: `docs/colab/dpo_training_template.ipynb`

**Interfaces:**
- Consumes: nothing (static artifact; references the URLs the admin pastes
  in manually).
- Produces: nothing consumed by other tasks — this is the deliverable
  itself.

- [ ] **Step 1: Write the notebook**

Create `docs/colab/dpo_training_template.ipynb` with this exact JSON
content:

```json
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# EquipED DPO Training Template\n",
    "\n",
    "Before running: open the EquipED admin panel, go to **Training Data**\n",
    "for the agent you're training, click **Start Training Job**, and paste\n",
    "the resulting `download_url` and `upload_url` below.\n",
    "\n",
    "This notebook does not include the actual LoRA/PEFT training loop --\n",
    "fill that in under the `# TODO` cell based on your chosen base model\n",
    "and hyperparameters."
   ]
  },
  {
   "cell_type": "code",
   "metadata": {},
   "source": [
    "DOWNLOAD_URL = \"PASTE_DOWNLOAD_URL_HERE\"\n",
    "UPLOAD_URL = \"PASTE_UPLOAD_URL_HERE\""
   ],
   "outputs": [],
   "execution_count": null
  },
  {
   "cell_type": "code",
   "metadata": {},
   "source": [
    "import io\n",
    "import json\n",
    "import zipfile\n",
    "\n",
    "import requests\n",
    "\n",
    "response = requests.get(DOWNLOAD_URL)\n",
    "response.raise_for_status()\n",
    "\n",
    "with zipfile.ZipFile(io.BytesIO(response.content)) as zf:\n",
    "    pairs = [json.loads(line) for line in zf.read(\"pairs.jsonl\").decode(\"utf-8\").splitlines() if line]\n",
    "    manifest = json.loads(zf.read(\"manifest.json\").decode(\"utf-8\"))\n",
    "\n",
    "print(f\"Loaded {len(pairs)} DPO pairs for agent={manifest['agent_id']}\")"
   ],
   "outputs": [],
   "execution_count": null
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Training\n",
    "\n",
    "TODO: your LoRA/PEFT training loop here. `pairs` is a list of dicts with\n",
    "`prompt`, `chosen`, `rejected` keys. Produce a trained adapter directory\n",
    "(e.g. containing `adapter_config.json` and adapter weights), then zip it\n",
    "before running the push-back cell below."
   ]
  },
  {
   "cell_type": "code",
   "metadata": {},
   "source": [
    "# TODO: base model choice, tokenizer, PEFT/LoRA config, training loop.\n",
    "# When training completes, set ADAPTER_DIR to the directory containing\n",
    "# the trained adapter's output files.\n",
    "ADAPTER_DIR = \"./trained_adapter\""
   ],
   "outputs": [],
   "execution_count": null
  },
  {
   "cell_type": "code",
   "metadata": {},
   "source": [
    "import os\n",
    "import zipfile as zf_module\n",
    "\n",
    "ADAPTER_ZIP_PATH = \"trained_adapter.zip\"\n",
    "with zf_module.ZipFile(ADAPTER_ZIP_PATH, mode=\"w\", compression=zf_module.ZIP_DEFLATED) as zf:\n",
    "    for root, _dirs, files in os.walk(ADAPTER_DIR):\n",
    "        for name in files:\n",
    "            full_path = os.path.join(root, name)\n",
    "            zf.write(full_path, arcname=name)\n",
    "\n",
    "with open(ADAPTER_ZIP_PATH, \"rb\") as f:\n",
    "    upload_response = requests.post(\n",
    "        UPLOAD_URL,\n",
    "        files={\"file\": (\"adapter.zip\", f, \"application/zip\")},\n",
    "    )\n",
    "upload_response.raise_for_status()\n",
    "print(\"Adapter uploaded:\", upload_response.json())"
   ],
   "outputs": [],
   "execution_count": null
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.12"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Verify it's valid JSON / a valid notebook**

Run: `cd /c/Users/Admin/Desktop/PROJECTS/EquipED && python -c "import json; json.load(open('docs/colab/dpo_training_template.ipynb'))"`
Expected: no output, exit code 0

- [ ] **Step 3: Commit**

```bash
git add docs/colab/dpo_training_template.ipynb
git commit -m "docs(training-data): add Colab DPO training notebook template"
```

---

### Task 10: Frontend types + API client

**Files:**
- Create: `apps/admin/src/features/training-data/types.ts`
- Create: `apps/admin/src/features/training-data/api/trainingData.api.ts`

**Interfaces:**
- Consumes: `requestJson` from `@equiped/api-client` (existing).
- Produces: `TrainingJobItem`, `TrainingJobListResponse`,
  `TrainingJobCreateResponse`, `TrainedAdapterItem`,
  `TrainedAdapterListResponse` (types.ts); `trainingDataApi.startJob(agentId)`,
  `.listJobs(agentId)`, `.listAdapters(agentId)` (api client). Later tasks
  (hooks) import both.

- [ ] **Step 1: Write `types.ts`**

```typescript
export interface TrainingJobItem {
  job_id: string;
  agent_id: string;
  status: 'pending' | 'downloaded' | 'completed';
  created_at: string;
}

export interface TrainingJobListResponse {
  agent_id: string;
  jobs: TrainingJobItem[];
}

export interface TrainingJobCreateResponse {
  job_id: string;
  agent_id: string;
  status: string;
  download_url: string;
  upload_url: string;
  download_expires_at: string;
  upload_expires_at: string;
  created_at: string;
}

export interface TrainedAdapterItem {
  adapter_id: string;
  agent_id: string;
  job_id: string;
  version: number;
  file_sha256: string;
  size_bytes: number;
  created_at: string;
}

export interface TrainedAdapterListResponse {
  agent_id: string;
  adapters: TrainedAdapterItem[];
}
```

- [ ] **Step 2: Write the API client**

```typescript
import { requestJson } from '@equiped/api-client';
import type {
  TrainedAdapterListResponse,
  TrainingJobCreateResponse,
  TrainingJobListResponse,
} from '../types';

export const trainingDataApi = {
  startJob: (agentId: string) =>
    requestJson<TrainingJobCreateResponse>(`/admin/training-data/${agentId}/jobs`, {
      method: 'POST',
    }),
  listJobs: (agentId: string) =>
    requestJson<TrainingJobListResponse>(`/admin/training-data/${agentId}/jobs`),
  listAdapters: (agentId: string) =>
    requestJson<TrainedAdapterListResponse>(`/admin/training-data/${agentId}/adapters`),
};
```

- [ ] **Step 3: Verify it type-checks**

Run: `pnpm --filter admin typecheck`
Expected: no errors related to the new files

- [ ] **Step 4: Commit**

```bash
git add apps/admin/src/features/training-data/types.ts apps/admin/src/features/training-data/api/trainingData.api.ts
git commit -m "feat(admin): add training-data types and API client"
```

---

### Task 11: Frontend hooks

**Files:**
- Create: `apps/admin/src/features/training-data/hooks/useTrainingJobs.ts`
- Create: `apps/admin/src/features/training-data/hooks/useTrainedAdapters.ts`
- Create: `apps/admin/src/features/training-data/hooks/useStartTrainingJob.ts`

**Interfaces:**
- Consumes: `trainingDataApi` (Task 10).
- Produces: `useTrainingJobs(agentId: string)`, `useTrainedAdapters(agentId: string)`
  (both `useQuery` wrappers), `useStartTrainingJob(agentId: string)` (a
  `useMutation` wrapper that invalidates the jobs query on success). Later
  tasks (components) call these.

- [ ] **Step 1: Write `useTrainingJobs.ts`**

```typescript
import { useQuery } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

export function useTrainingJobs(agentId: string) {
  return useQuery({
    queryKey: ['trainingJobs', agentId],
    queryFn: () => trainingDataApi.listJobs(agentId),
  });
}
```

- [ ] **Step 2: Write `useTrainedAdapters.ts`**

```typescript
import { useQuery } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

export function useTrainedAdapters(agentId: string) {
  return useQuery({
    queryKey: ['trainedAdapters', agentId],
    queryFn: () => trainingDataApi.listAdapters(agentId),
  });
}
```

- [ ] **Step 3: Write `useStartTrainingJob.ts`**

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

export function useStartTrainingJob(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => trainingDataApi.startJob(agentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['trainingJobs', agentId] });
    },
  });
}
```

- [ ] **Step 4: Verify it type-checks**

Run: `pnpm --filter admin typecheck`
Expected: no errors related to the new files

- [ ] **Step 5: Commit**

```bash
git add apps/admin/src/features/training-data/hooks/
git commit -m "feat(admin): add training-data TanStack Query hooks"
```

---

### Task 12: Frontend components + page

**Files:**
- Create: `apps/admin/src/features/training-data/components/TrainingJobsPanel.tsx`
- Create: `apps/admin/src/features/training-data/components/AdapterListTable.tsx`
- Create: `apps/admin/src/features/training-data/components/__tests__/TrainingJobsPanel.test.tsx`
- Create: `apps/admin/src/features/training-data/pages/TrainingDataPage.tsx`

**Interfaces:**
- Consumes: `useTrainingJobs, useStartTrainingJob` (Task 11) in
  `TrainingJobsPanel`; `useTrainedAdapters` (Task 11) in
  `AdapterListTable`; `Button`, `Badge` from `@equiped/ui` (existing, used
  by `AgentPromptEditor`); `useParams` from `@tanstack/react-router`
  (existing pattern, see `AgentPromptEditor.tsx`).
- Produces: `TrainingDataPage` component, the page-level export the router
  (Task 13) mounts.

- [ ] **Step 1: Write the failing component test**

```typescript
// apps/admin/src/features/training-data/components/__tests__/TrainingJobsPanel.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { TrainingJobsPanel } from '../TrainingJobsPanel';
import { trainingDataApi } from '../../api/trainingData.api';

vi.mock('../../api/trainingData.api', () => ({
  trainingDataApi: {
    listJobs: vi.fn(),
    startJob: vi.fn(),
    listAdapters: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe('TrainingJobsPanel', () => {
  beforeEach(() => {
    vi.mocked(trainingDataApi.listJobs).mockResolvedValue({
      agent_id: 'gad',
      jobs: [],
    });
  });

  it('renders a Start Training Job button', async () => {
    renderWithClient(<TrainingJobsPanel agentId="gad" />);
    expect(await screen.findByRole('button', { name: /start training job/i })).toBeInTheDocument();
  });

  it('shows download and upload URLs after starting a job', async () => {
    vi.mocked(trainingDataApi.startJob).mockResolvedValue({
      job_id: 'job-1',
      agent_id: 'gad',
      status: 'pending',
      download_url: 'https://example.test/download?token=abc',
      upload_url: 'https://example.test/upload?token=def',
      download_expires_at: new Date().toISOString(),
      upload_expires_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
    });

    renderWithClient(<TrainingJobsPanel agentId="gad" />);
    const button = await screen.findByRole('button', { name: /start training job/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/https:\/\/example\.test\/download/)).toBeInTheDocument();
      expect(screen.getByText(/https:\/\/example\.test\/upload/)).toBeInTheDocument();
    });
  });
});
```

Check `apps/admin/src/features/preference-log/components/__tests__/PreferenceLogTable.test.tsx`
(already listed in the file structure of this feature earlier in this
session) for the exact test-setup conventions this project uses (render
helpers, `vi.mock` shape, whether a shared test-utils wrapper already
exists) and align this test to match exactly rather than inventing new
conventions.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter admin test -- TrainingJobsPanel`
Expected: FAIL — `TrainingJobsPanel` module not found

- [ ] **Step 3: Write `TrainingJobsPanel.tsx`**

```typescript
import { useState } from 'react';
import { Button } from '@equiped/ui';
import { useStartTrainingJob } from '../hooks/useStartTrainingJob';
import { useTrainingJobs } from '../hooks/useTrainingJobs';
import type { TrainingJobCreateResponse } from '../types';

export function TrainingJobsPanel({ agentId }: { agentId: string }) {
  const { data } = useTrainingJobs(agentId);
  const startJob = useStartTrainingJob(agentId);
  const [lastCreated, setLastCreated] = useState<TrainingJobCreateResponse | null>(null);

  const handleStart = () => {
    startJob.mutate(undefined, {
      onSuccess: (result) => setLastCreated(result),
    });
  };

  return (
    <div className="space-y-4">
      <Button onClick={handleStart} disabled={startJob.isPending}>
        {startJob.isPending ? 'Starting…' : 'Start Training Job'}
      </Button>

      {lastCreated && (
        <div className="rounded border border-neutral-200 p-4 space-y-2 text-sm">
          <p>
            <strong>Download URL</strong> (paste into notebook cell 1, expires{' '}
            {new Date(lastCreated.download_expires_at).toLocaleString()}):
          </p>
          <code className="block break-all">{lastCreated.download_url}</code>
          <p>
            <strong>Upload URL</strong> (paste into notebook's last cell, expires{' '}
            {new Date(lastCreated.upload_expires_at).toLocaleString()}):
          </p>
          <code className="block break-all">{lastCreated.upload_url}</code>
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            <th>Job ID</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {(data?.jobs ?? []).map((job) => (
            <tr key={job.job_id}>
              <td>{job.job_id}</td>
              <td>{job.status}</td>
              <td>{new Date(job.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter admin test -- TrainingJobsPanel`
Expected: PASS

- [ ] **Step 5: Write `AdapterListTable.tsx`**

```typescript
import { useTrainedAdapters } from '../hooks/useTrainedAdapters';

export function AdapterListTable({ agentId }: { agentId: string }) {
  const { data } = useTrainedAdapters(agentId);

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left">
          <th>Version</th>
          <th>Uploaded</th>
          <th>Size</th>
          <th>Hash</th>
          <th>Source Job</th>
        </tr>
      </thead>
      <tbody>
        {(data?.adapters ?? []).map((adapter) => (
          <tr key={adapter.adapter_id}>
            <td>{adapter.version}</td>
            <td>{new Date(adapter.created_at).toLocaleString()}</td>
            <td>{(adapter.size_bytes / (1024 * 1024)).toFixed(1)} MB</td>
            <td>{adapter.file_sha256.slice(0, 12)}…</td>
            <td>{adapter.job_id}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 6: Write `TrainingDataPage.tsx`**

Follow `AgentPromptEditor.tsx`'s `useParams({ strict: false })` +
`AGENTS` array pattern exactly:

```typescript
import { useParams } from '@tanstack/react-router';
import { AdapterListTable } from '../components/AdapterListTable';
import { TrainingJobsPanel } from '../components/TrainingJobsPanel';

const AGENTS = [
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'gad', label: 'Gender & Development (GAD)' },
  { id: 'itso', label: 'Intellectual Property (ITSO)' },
] as const;

export function TrainingDataPage() {
  const { agentId } = useParams({ strict: false }) as { agentId?: string };
  const activeAgent = agentId ?? 'coordinator';
  const activeAgentMeta = AGENTS.find((a) => a.id === activeAgent) ?? AGENTS[0];

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-8">
      <h1 className="text-xl font-semibold">{activeAgentMeta.label} — Training Data</h1>
      <TrainingJobsPanel agentId={activeAgent} />
      <h2 className="text-lg font-semibold">Trained Adapters</h2>
      <AdapterListTable agentId={activeAgent} />
    </section>
  );
}
```

- [ ] **Step 7: Run the full admin test suite to check for regressions**

Run: `pnpm --filter admin test`
Expected: all pass, no new failures

- [ ] **Step 8: Commit**

```bash
git add apps/admin/src/features/training-data/components/ apps/admin/src/features/training-data/pages/
git commit -m "feat(admin): add training-data page, job panel, and adapter list components"
```

---

### Task 13: Router registration + navigation

**Files:**
- Modify: `apps/admin/src/app/router.tsx`
- Modify: `apps/admin/src/app/layout/navigation.utils.ts`

**Interfaces:**
- Consumes: `TrainingDataPage` (Task 12).
- Produces: `/admin/training-data` (default-redirects to `coordinator`,
  matching `adminPromptsRoute`'s pattern) and `/admin/training-data/$agentId`
  routes; a "Training Data" nav item; breadcrumb and page-title entries.

- [ ] **Step 1: Add the lazy route component**

In `apps/admin/src/app/router.tsx`, alongside the other `lazyRouteComponent`
declarations, add:

```typescript
const TrainingDataPage = lazyRouteComponent(
  () => import('../features/training-data/pages/TrainingDataPage'),
  'TrainingDataPage',
);
```

- [ ] **Step 2: Add the routes**

Following the exact shape of `adminPromptsRoute` +
`adminPromptDetailRoute`, add:

```typescript
const adminTrainingDataRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'training-data',
  beforeLoad: ({ location }) => {
    if (location.pathname === '/admin/training-data') {
      throw redirect({ to: '/admin/training-data/$agentId', params: { agentId: 'coordinator' } });
    }
  },
  component: Outlet,
});

const adminTrainingDataDetailRoute = createRoute({
  getParentRoute: () => adminTrainingDataRoute,
  path: '$agentId',
  component: TrainingDataPage,
});
```

Add both to the route tree's `adminRoute.addChildren([...])` array:
`adminTrainingDataRoute.addChildren([adminTrainingDataDetailRoute])`.

- [ ] **Step 3: Add the nav item, breadcrumb, and title**

In `apps/admin/src/app/layout/navigation.utils.ts`:

1. Import an icon for it (e.g. `Robot` or another available
   `@phosphor-icons/react` icon distinct from the ones already used — check
   the existing import list and pick one that reads well for "training
   data"; `Cpu` or `GraduationCap` are reasonable choices if available in
   the installed `@phosphor-icons/react` version).
2. Add a nav item to the `model-governance` group:
   `{ to: '/admin/training-data', label: 'Training Data', icon: <ChosenIcon>, exact: false }`.
3. Add a breadcrumb branch in `getBreadcrumbs`:

```typescript
if (cleanPath === '/admin/training-data' || cleanPath.startsWith('/admin/training-data/')) {
  return [
    { label: 'Administration', to: '/admin' },
    { label: 'Training Data' },
  ];
}
```

4. Add a title branch in `getRouteTitle`:

```typescript
if (cleanPath.startsWith('/admin/training-data')) return 'Training Data';
```

- [ ] **Step 4: Verify the icon exists in the installed package**

Run: `pnpm --filter admin typecheck`
Expected: no errors — if the chosen icon name doesn't exist in
`@phosphor-icons/react`, this will surface as a type error; pick a
different icon from ones already imported elsewhere in the admin app if so.

- [ ] **Step 5: Run the admin test suite**

Run: `pnpm --filter admin test`
Expected: all pass, no new failures (check
`apps/admin/src/app/__tests__/router.test.ts` and
`apps/admin/src/app/layout/__tests__/navigation.test.ts` specifically,
since both were found referencing nav/route conventions earlier — they may
assert on the full nav item list or route tree shape and need a matching
update for the new entry)

- [ ] **Step 6: Manually verify in the dev server**

Run: `pnpm dev:admin`, log in as an admin user, navigate to
"Training Data" in the sidebar, confirm the page loads, the agent
switch works via URL (`/admin/training-data/gad`), and clicking
"Start Training Job" (with at least one `gad_scores.v1` generation
already in the dev DB from earlier GAD testing this session) returns
a job with download/upload URLs.

- [ ] **Step 7: Commit**

```bash
git add apps/admin/src/app/router.tsx apps/admin/src/app/layout/navigation.utils.ts
git commit -m "feat(admin): register training-data route and navigation entry"
```

---

## Self-Review Notes

**Spec coverage:**
- Start-job endpoint + dataset freezing → Task 4.
- Download endpoint (token-authenticated, no session) → Task 5, Task 8.
- Upload endpoint + adapter storage → Task 6, Task 8.
- Job list / adapter list endpoints → Task 7, Task 8.
- Admin UI (start action, job list, adapter list, per-agent) → Tasks 10-13.
- Colab notebook template → Task 9.
- Error handling (404 on any token failure, size/extension checks) → Task 5,
  Task 6, exercised in Task 8's router tests.
- Testing section's backend/frontend coverage → present across Tasks 1-13.
- Non-goals (LoRA training code, active-adapter flag, automating Colab
  itself) → deliberately absent from every task; Task 9's notebook leaves
  the training loop as an explicit TODO.

**Type consistency check:** `TrainingJobCreated` (Task 4) →
`.job.job_id`, `.raw_download_token`, `.raw_upload_token` used identically
in Task 5, Task 8. `DpoTrainingJob.status` values (`pending`, `downloaded`,
`completed`) match across the model (Task 1), the CheckConstraint (Task 1),
and every place a status string literal appears (Tasks 4, 5, 6). Frontend
`TrainingJobItem.status` union type (Task 10) matches those same three
values.

**Open items carried from the spec, not resolved here (by design):**
File-size cap defaulted to 500 MB in Task 6 (spec left this as "TBD during
planning" — this plan makes the call so no task has a placeholder; revisit
if it's wrong). Whether to extend `preference-log` vs. add a sibling
feature was resolved as "add a sibling feature" (`training-data`) — cleaner
boundary, matches the spec's stated open question being left to planning
time.
