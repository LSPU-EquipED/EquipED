# DPO-Based ITSO Scoring Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let CID reviewers Accept/Reject/Edit each ITSO criterion's score + justification on the evaluation Scorecard, persist that feedback per-agent/per-criterion, and export EDIT actions as DPO training pairs — with model training itself staying a manual, offline, out-of-repo step.

**Architecture:** A new `POST /feedback/{evaluation_id}/criteria/{criterion_id}` endpoint writes to an extended `PreferenceLog` table (adds `agent_name`, `criterion_id`). ITSO's assembled prompt is snapshotted verbatim onto `AgentResult.prompt_text` at scoring time (a new nullable column, populated only for ITSO) so the export step never has to replay prompt-building logic. A read-only export script joins EDIT rows against that snapshot to produce `(prompt, chosen, rejected)` JSONL. The Scorecard UI gains inline Accept/Reject/Edit controls, but only on ITSO's criterion rows.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (Python 3.12, ruff), React 18 + TanStack Query/Router + Tailwind v4 (TypeScript, ESLint/Prettier).

## Global Constraints

- Backend: ruff-enforced (E, F, I, UP), line length 88, Python 3.12. Per-module layout (`router.py`, `service.py`, `models.py`, `schemas.py`, `exceptions.py`); business rules stay in modules, not `core/`.
- Frontend: TypeScript, ESLint (react-hooks, react-refresh) + Prettier. No shadcn/ui or external component kits — components are custom-built.
- This phase is scoped to the **ITSO** agent only. GAD/SME/Coordinator are explicitly out of scope (see `docs/superpowers/specs/2026-08-10-dpo-itso-scoring-design.md`, Phase 2).
- Feedback endpoints are restricted to `UserRole.ADMIN` (`server/modules/auth/models.py` — there is no separate CID-reviewer role today), matching the existing `GET /admin/preferences` gating.
- Run backend commands from the repo root with `--project server` (e.g. `uv run --project server pytest`), never from inside `server/`.
- Model training/deployment is explicitly out of scope for this plan — it ends at a JSONL export file.

---

### Task 1: Extend `PreferenceLog` with `agent_name` and `criterion_id`

**Files:**
- Modify: `server/modules/feedback/models.py`
- Create: `server/alembic/versions/20260810_0001_add_preference_log_attribution.py`
- Test: `server/tests/feedback/test_models.py` (new file, new `server/tests/feedback/__init__.py`)

**Interfaces:**
- Produces: `PreferenceLog.agent_name: str | None`, `PreferenceLog.criterion_id: str | None` — later tasks (service layer, admin schema) read/write these two columns directly on the ORM model.

- [ ] **Step 1: Write the failing test**

Create `server/tests/feedback/__init__.py` (empty file) and `server/tests/feedback/test_models.py`:

```python
"""Persistence tests for the extended PreferenceLog model."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.auth.models import User, UserRole
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog


def test_preference_log_stores_agent_and_criterion_attribution(db_session):
    user = User(
        user_id=uuid4(),
        name="Admin",
        email="admin@example.com",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.flush()

    # Document.uploaded_by is a required (non-nullable) FK to users.user_id,
    # so the user above must be created and flushed first.
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()

    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    log = PreferenceLog(
        evaluation_id=job.evaluation_id,
        user_id=user.user_id,
        agent_name="itso",
        criterion_id="itso-03",
        action="EDIT",
        edited_json={"score": 2, "justification": "Missing citation format check."},
    )
    db_session.add(log)
    db_session.commit()

    fetched = db_session.get(PreferenceLog, log.log_id)
    assert fetched.agent_name == "itso"
    assert fetched.criterion_id == "itso-03"
    assert fetched.edited_json == {
        "score": 2,
        "justification": "Missing citation format check.",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/feedback/test_models.py -v`
Expected: FAIL — `TypeError: 'agent_name' is an invalid keyword argument for PreferenceLog` (columns don't exist yet).

- [ ] **Step 3: Add the columns to the model**

In `server/modules/feedback/models.py`, add two columns after `user_id` and before `action`:

```python
    agent_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    criterion_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/feedback/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Write the Alembic migration**

Run `uv run --project server alembic -c server/alembic.ini heads` from the repo root to find the current migration head(s). If there is more than one head, stop and ask — do not guess which to chain onto. Otherwise, create `server/alembic/versions/20260810_0001_add_preference_log_attribution.py` with `down_revision` set to that head's revision id (replace `<CURRENT_HEAD>` below with it):

```python
"""add agent_name/criterion_id to preference_logs

Revision ID: 20260810_0001
Revises: <CURRENT_HEAD>
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260810_0001"
down_revision = "<CURRENT_HEAD>"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if not _has_column("preference_logs", "agent_name"):
        op.add_column(
            "preference_logs", sa.Column("agent_name", sa.String(length=32), nullable=True)
        )
    if not _has_column("preference_logs", "criterion_id"):
        op.add_column(
            "preference_logs",
            sa.Column("criterion_id", sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    if _has_column("preference_logs", "criterion_id"):
        op.drop_column("preference_logs", "criterion_id")
    if _has_column("preference_logs", "agent_name"):
        op.drop_column("preference_logs", "agent_name")
```

- [ ] **Step 6: Commit**

```bash
git add server/modules/feedback/models.py server/alembic/versions/20260810_0001_add_preference_log_attribution.py server/tests/feedback/__init__.py server/tests/feedback/test_models.py
git commit -m "feat(feedback): add agent_name/criterion_id to PreferenceLog"
```

---

### Task 2: Persist the ITSO prompt snapshot on `AgentResult`

**Files:**
- Modify: `server/modules/agents/contracts.py`
- Modify: `server/modules/agents/itso/execution.py:133-167` (the `AgentEvaluationResult(...)` return)
- Modify: `server/modules/synthesis/models.py`
- Modify: `server/modules/synthesis/service.py:44-63` (failure branch), `:66-82` (success branch)
- Create: `server/alembic/versions/20260810_0002_add_agent_result_prompt_text.py`
- Test: `server/tests/agents/itso/test_itso_execution.py` (add one test)

**Interfaces:**
- Consumes: `PreferenceLog` from Task 1 is not touched here — this task is independent of Task 1.
- Produces: `AgentEvaluationResult.prompt_text: str | None`, `AgentResult.prompt_text: str | None` (Text column) — Task 7's export script reads `AgentResult.prompt_text` directly instead of re-deriving the prompt.

Why a dedicated column and not `provenance`: `server/modules/agents/provenance.py`'s `sanitize_provenance` is a strict allowlist that silently drops any key not in `PROVENANCE_ALLOWLIST` and is explicitly designed to "never leak raw text." The full ITSO prompt (rubric + reference + document chunk text) is exactly the kind of raw text that sanitizer exists to keep out of `provenance`. `raw_response` (the model's raw output) already bypasses that sanitizer by living in its own column — `prompt_text` mirrors that existing pattern for the input side.

- [ ] **Step 1: Write the failing test**

Add to `server/tests/agents/itso/test_itso_execution.py` (reuses the file's existing `_context`, `_LLM`, `_response`, `_settings` helpers):

```python
def test_itso_executes_and_snapshots_prompt_text(monkeypatch):
    monkeypatch.setattr(execution, "get_settings", lambda: _settings())
    result = execution.execute(
        _context(_LLM([_response("ok")]))
    )
    assert result.prompt_text is not None
    assert '"agent": "itso"' in result.prompt_text
    assert '"criterion_scores"' not in result.prompt_text
```

(The last assertion distinguishes the *prompt* sent to the model — which asks for `criterion_scores` in its instructions text but never contains that literal JSON key in the assembled payload — from the model's *response*; if this assertion is flaky against real prompt content, drop it and keep only the first two.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/agents/itso/test_itso_execution.py::test_itso_executes_and_snapshots_prompt_text -v`
Expected: FAIL — `AttributeError: 'AgentEvaluationResult' object has no attribute 'prompt_text'`

- [ ] **Step 3: Add `prompt_text` to the `AgentEvaluationResult` contract**

In `server/modules/agents/contracts.py`, add a field to `AgentEvaluationResult` (after `raw_response`):

```python
    raw_response: str | None = None
    prompt_text: str | None = None
```

- [ ] **Step 4: Populate it in ITSO's execution path**

In `server/modules/agents/itso/execution.py`, the `execute()` function already builds the full prompt into the local variable `prompt` (see line 55: `prompt = build_prompt(...)`, later trimmed via `budget.prompt` at line 62). In the `return AgentEvaluationResult(...)` block (currently lines 133-167), add:

```python
        raw_response=raw,
        prompt_text=prompt,
        provenance=safe,
```

(insert `prompt_text=prompt,` immediately after the existing `raw_response=raw,` line)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/agents/itso/test_itso_execution.py -v`
Expected: PASS (all tests in the file, including the new one)

- [ ] **Step 6: Add the column to `AgentResult` and wire persistence**

In `server/modules/synthesis/models.py`, add to `AgentResult` (after `raw_response`):

```python
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
```

In `server/modules/synthesis/service.py`, `persist_agent_outputs` builds two `AgentResult(...)` rows — one for the failure branch (currently lines 45-61) and one for the success branch (currently lines 66-81). Add `prompt_text=agent_result.prompt_text,` to **both**, right after each block's `raw_response=agent_result.raw_response,` line.

- [ ] **Step 7: Write the Alembic migration**

Run `uv run --project server alembic -c server/alembic.ini heads` again — the head is now `20260810_0001` from Task 1 (assuming Task 1 was applied/committed first; if executing tasks out of order, use whatever `alembic heads` actually reports). Create `server/alembic/versions/20260810_0002_add_agent_result_prompt_text.py`:

```python
"""add prompt_text to agent_results

Revision ID: 20260810_0002
Revises: 20260810_0001
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260810_0002"
down_revision = "20260810_0001"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if _has_column("agent_results", "prompt_text"):
        return
    op.add_column("agent_results", sa.Column("prompt_text", sa.Text(), nullable=True))


def downgrade() -> None:
    if not _has_column("agent_results", "prompt_text"):
        return
    op.drop_column("agent_results", "prompt_text")
```

- [ ] **Step 8: Run the full agents + synthesis test suites to check nothing else broke**

Run: `uv run --project server pytest server/tests/agents server/tests/synthesis -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add server/modules/agents/contracts.py server/modules/agents/itso/execution.py server/modules/synthesis/models.py server/modules/synthesis/service.py server/alembic/versions/20260810_0002_add_agent_result_prompt_text.py server/tests/agents/itso/test_itso_execution.py
git commit -m "feat(agents): snapshot ITSO's assembled prompt onto AgentResult"
```

---

### Task 3: Feedback service, schemas, and the criterion-feedback endpoint

**Files:**
- Create: `server/modules/feedback/exceptions.py`
- Modify: `server/modules/feedback/schemas.py`
- Modify: `server/modules/feedback/service.py`
- Modify: `server/modules/feedback/router.py`
- Test: `server/tests/feedback/test_router.py` (new)
- Test: `server/tests/feedback/conftest.py` (new)

**Interfaces:**
- Consumes: `PreferenceLog.agent_name`/`criterion_id` from Task 1. `require_admin` from `server/modules/auth/dependencies.py` (existing). `get_db_session` from `server/core/database.py` (existing).
- Produces: `create_criterion_feedback(db, *, evaluation_id, criterion_id, agent_name, action, user_id, score=None, justification=None, notes=None) -> PreferenceLog` in `feedback/service.py` — used directly by the router in this task; no other task depends on it.
- Produces: `POST /api/v1/feedback/{evaluation_id}/criteria/{criterion_id}` — Task 5/6 (frontend) call this exact path and body shape.

- [ ] **Step 1: Write the failing test**

Create `server/tests/feedback/conftest.py`:

```python
"""Shared fixtures for feedback module tests."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.tests.admin.conftest import admin_user  # noqa: F401 — re-exported fixture


@pytest.fixture()
def evaluation_job(db_session, admin_user):
    # Document.uploaded_by is a required (non-nullable) FK to users.user_id,
    # so this fixture depends on admin_user rather than passing None.
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=admin_user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()
    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.commit()
    return job
```

Create `server/tests/feedback/test_router.py`:

```python
"""Criterion feedback endpoint: access control and behavior."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.modules.feedback.models import PreferenceLog
from server.tests.admin.conftest import _auth


def test_criterion_feedback_requires_admin(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin, evaluation_job
):
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"
    body = {"agent_name": "itso", "action": "ACCEPT"}

    response = client.post(url, json=body)
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.post(url, json=body)
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.post(url, json=body)
    assert response.status_code == 201


def test_criterion_feedback_edit_requires_score_and_justification(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"

    response = client.post(url, json={"agent_name": "itso", "action": "EDIT"})
    assert response.status_code == 422

    response = client.post(
        url,
        json={
            "agent_name": "itso",
            "action": "EDIT",
            "score": 2,
            "justification": "Reviewer correction: no bibliography section found.",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["agent_name"] == "itso"
    assert body["criterion_id"] == "itso-03"
    assert body["action"] == "EDIT"
    assert body["edited_json"] == {
        "score": 2,
        "justification": "Reviewer correction: no bibliography section found.",
    }


def test_criterion_feedback_unknown_evaluation_returns_404(
    client: TestClient, auth_cookies_admin
):
    _auth(client, auth_cookies_admin)
    import uuid

    url = f"/api/v1/feedback/{uuid.uuid4()}/criteria/itso-03"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 404


def test_criterion_feedback_persists_row(
    client: TestClient, auth_cookies_admin, evaluation_job, admin_user, db_session
):
    _auth(client, auth_cookies_admin)
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"
    client.post(url, json={"agent_name": "itso", "action": "REJECT", "notes": "wrong"})

    rows = db_session.query(PreferenceLog).all()
    assert len(rows) == 1
    assert rows[0].agent_name == "itso"
    assert rows[0].criterion_id == "itso-03"
    assert rows[0].action == "REJECT"
    assert rows[0].notes == "wrong"
    assert rows[0].user_id == admin_user.user_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/feedback/test_router.py -v`
Expected: FAIL — 404s (no route registered) or import errors, since the endpoint doesn't exist yet.

- [ ] **Step 3: Create `feedback/exceptions.py`**

```python
"""Exceptions raised by the feedback module."""

from __future__ import annotations


class EvaluationNotFoundError(Exception):
    """Raised when feedback targets an evaluation_id that doesn't exist."""


__all__ = ["EvaluationNotFoundError"]
```

- [ ] **Step 4: Write `feedback/schemas.py`** (replace the placeholder file entirely)

```python
"""Pydantic schemas for criterion-level feedback."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CriterionFeedbackCreate(BaseModel):
    """Request body for POST /feedback/{evaluation_id}/criteria/{criterion_id}.

    Phase 1 scope: agent_name is restricted to "itso" — the only agent
    whose score+justification come from a single LLM generation and can
    therefore produce a coherent DPO pair. See
    docs/superpowers/specs/2026-08-10-dpo-itso-scoring-design.md.
    """

    agent_name: Literal["itso"]
    action: Literal["ACCEPT", "REJECT", "EDIT"]
    score: int | None = Field(default=None, ge=1, le=4)
    justification: str | None = Field(default=None, min_length=1, max_length=4000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _edit_requires_score_and_justification(self) -> "CriterionFeedbackCreate":
        if self.action == "EDIT" and (self.score is None or not self.justification):
            raise ValueError(
                "EDIT actions require both 'score' and 'justification' so the "
                "correction is internally consistent."
            )
        return self


class CriterionFeedbackResponse(BaseModel):
    log_id: uuid.UUID
    evaluation_id: uuid.UUID
    user_id: uuid.UUID
    agent_name: str | None
    criterion_id: str | None
    action: Literal["ACCEPT", "REJECT", "EDIT"]
    edited_json: dict | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


__all__ = ["CriterionFeedbackCreate", "CriterionFeedbackResponse"]
```

- [ ] **Step 5: Add `create_criterion_feedback` to `feedback/service.py`**

Add to the existing `server/modules/feedback/service.py` (keep the existing `list_preference_logs` function as-is):

```python
import uuid

from server.modules.evaluations.models import EvaluationJob

from .exceptions import EvaluationNotFoundError


def create_criterion_feedback(
    db: Session,
    *,
    evaluation_id: uuid.UUID,
    criterion_id: str,
    agent_name: str,
    action: str,
    user_id: uuid.UUID,
    score: int | None = None,
    justification: str | None = None,
    notes: str | None = None,
) -> PreferenceLog:
    """Persist one reviewer feedback action for one agent's criterion.

    Raises EvaluationNotFoundError if evaluation_id doesn't exist.
    """

    if db.get(EvaluationJob, evaluation_id) is None:
        raise EvaluationNotFoundError(f"Evaluation {evaluation_id} not found")

    edited_json = (
        {"score": score, "justification": justification}
        if action == "EDIT"
        else None
    )

    log = PreferenceLog(
        evaluation_id=evaluation_id,
        user_id=user_id,
        agent_name=agent_name,
        criterion_id=criterion_id,
        action=action,
        edited_json=edited_json,
        notes=notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
```

(Add the `import uuid`, `from server.modules.evaluations.models import EvaluationJob`, and `from .exceptions import EvaluationNotFoundError` lines to the existing import block at the top of the file, alongside the existing `from sqlalchemy import desc` / `from sqlalchemy.orm import Session` / `from .models import PreferenceLog` imports.)

- [ ] **Step 6: Write the router endpoint** (replace the scaffold `feedback/router.py` entirely)

```python
"""Routes for the feedback module: criterion-level reviewer feedback."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin
from server.modules.auth.service import AuthenticatedUser
from server.modules.feedback.exceptions import EvaluationNotFoundError
from server.modules.feedback.schemas import (
    CriterionFeedbackCreate,
    CriterionFeedbackResponse,
)
from server.modules.feedback.service import create_criterion_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "/{evaluation_id}/criteria/{criterion_id}",
    response_model=CriterionFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_criterion_feedback(
    evaluation_id: uuid.UUID,
    criterion_id: str,
    body: CriterionFeedbackCreate,
    current_user: AuthenticatedUser = Depends(require_admin),
    db=Depends(get_db_session),
):
    try:
        log = create_criterion_feedback(
            db,
            evaluation_id=evaluation_id,
            criterion_id=criterion_id,
            agent_name=body.agent_name,
            action=body.action,
            user_id=current_user.id,
            score=body.score,
            justification=body.justification,
            notes=body.notes,
        )
    except EvaluationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    return CriterionFeedbackResponse(
        log_id=log.log_id,
        evaluation_id=log.evaluation_id,
        user_id=log.user_id,
        agent_name=log.agent_name,
        criterion_id=log.criterion_id,
        action=log.action,
        edited_json=log.edited_json,
        notes=log.notes,
        created_at=log.created_at,
    )


__all__ = ["router"]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/feedback -v`
Expected: PASS

- [ ] **Step 8: Lint**

Run: `uv run --project server ruff check server/modules/feedback server/tests/feedback`
Expected: no errors

- [ ] **Step 9: Commit**

```bash
git add server/modules/feedback/exceptions.py server/modules/feedback/schemas.py server/modules/feedback/service.py server/modules/feedback/router.py server/tests/feedback/conftest.py server/tests/feedback/test_router.py
git commit -m "feat(feedback): add per-criterion ACCEPT/REJECT/EDIT endpoint"
```

---

### Task 4: Surface `agent_name`/`criterion_id` on the admin preference log view

**Files:**
- Modify: `server/modules/admin/schemas.py:45-58` (`PreferenceLogResponse`)
- Modify: `server/modules/admin/router.py:180-196` (`get_preferences`)
- Test: `server/tests/admin/test_preferences.py` (new)

**Interfaces:**
- Consumes: `PreferenceLog.agent_name`/`criterion_id` from Task 1.
- Produces: `agent_name`/`criterion_id` fields on the existing `GET /admin/preferences` response — no other backend task depends on this; it's a display-only extension for the existing admin table.

- [ ] **Step 1: Write the failing test**

Create `server/tests/admin/test_preferences.py`:

```python
"""Admin preference log view: agent_name/criterion_id surfacing."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.modules.feedback.service import create_criterion_feedback
from server.tests.admin.conftest import _auth
from server.tests.evaluations.conftest import _add_document


def test_admin_preferences_include_agent_and_criterion(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    from server.modules.evaluations.models import EvaluationJob
    from uuid import uuid4

    document_id = _add_document(db_session, owner_id=admin_user.user_id, source_type="slm")
    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="ACCEPT",
        user_id=admin_user.user_id,
    )

    _auth(client, auth_cookies_admin)
    response = client.get("/api/v1/admin/preferences")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["agent_name"] == "itso"
    assert items[0]["criterion_id"] == "itso-03"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/admin/test_preferences.py -v`
Expected: FAIL — `KeyError: 'agent_name'` (field missing from response).

- [ ] **Step 3: Extend `PreferenceLogResponse`**

In `server/modules/admin/schemas.py`, add two fields to `PreferenceLogResponse` (after `user_id`):

```python
class PreferenceLogResponse(BaseModel):
    """A single preference log entry."""

    log_id: uuid.UUID
    evaluation_id: uuid.UUID
    user_id: uuid.UUID
    agent_name: str | None = None
    criterion_id: str | None = None
    action: Literal["ACCEPT", "REJECT", "EDIT"]
    edited_json: dict | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Populate the fields in the router**

In `server/modules/admin/router.py`, in `get_preferences`, add the two fields to the `PreferenceLogResponse(...)` construction:

```python
            PreferenceLogResponse(
                log_id=item.log_id,
                evaluation_id=item.evaluation_id,
                user_id=item.user_id,
                agent_name=item.agent_name,
                criterion_id=item.criterion_id,
                action=item.action,
                edited_json=item.edited_json,
                notes=item.notes,
                created_at=item.created_at,
            )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/admin/test_preferences.py -v`
Expected: PASS

- [ ] **Step 6: Run the full admin suite to check nothing else broke**

Run: `uv run --project server pytest server/tests/admin -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add server/modules/admin/schemas.py server/modules/admin/router.py server/tests/admin/test_preferences.py
git commit -m "feat(admin): surface agent_name/criterion_id on preference log view"
```

---

### Task 5: Frontend types, API client, and mutation hook

**Files:**
- Modify: `client/src/features/evaluation/types.ts`
- Modify: `client/src/features/evaluation/api/evaluation.api.ts`
- Modify: `client/src/features/evaluation/hooks/useSubmitFeedback.ts`
- Test: `client/src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.ts` (new)

**Interfaces:**
- Consumes: `POST /feedback/{evaluation_id}/criteria/{criterion_id}` from Task 3 (path and body shape must match exactly).
- Produces: `submitCriterionFeedback(evaluationId, criterionId, body)` in `evaluation.api.ts`, and `useSubmitCriterionFeedback(evaluationId)` hook — Task 6 imports and calls the hook directly.

- [ ] **Step 1: Add types**

In `client/src/features/evaluation/types.ts`, add at the end of the file:

```typescript
export type CriterionFeedbackAction = 'ACCEPT' | 'REJECT' | 'EDIT';

export interface CriterionFeedbackRequest {
  agent_name: 'itso';
  action: CriterionFeedbackAction;
  score?: number;
  justification?: string;
  notes?: string;
}

export interface CriterionFeedbackResponse {
  log_id: string;
  evaluation_id: string;
  user_id: string;
  agent_name: string | null;
  criterion_id: string | null;
  action: CriterionFeedbackAction;
  edited_json: { score: number; justification: string } | null;
  notes: string | null;
  created_at: string;
}
```

- [ ] **Step 2: Add the API client function**

In `client/src/features/evaluation/api/evaluation.api.ts`, add the import and a new function:

```typescript
import { requestJson } from '@/shared/api/http';
import type {
  EvaluationResponse,
  EvaluationResultsResponse,
  EvaluationStatusResponse,
  EvaluationListResponse,
  CriterionFeedbackRequest,
  CriterionFeedbackResponse,
} from '../types';

export const evaluationApi = {
  listEvaluations: async (documentId?: string): Promise<EvaluationListResponse> => {
    const params = documentId ? `?document_id=${encodeURIComponent(documentId)}` : '';
    return requestJson<EvaluationListResponse>(`/evaluations/${params}`);
  },

  getEvaluation: async (id: string): Promise<EvaluationResponse> => {
    return requestJson<EvaluationResponse>(`/evaluations/${id}`);
  },

  getEvaluationStatus: async (id: string): Promise<EvaluationStatusResponse> => {
    return requestJson<EvaluationStatusResponse>(`/evaluations/${id}/status`);
  },

  getEvaluationResults: async (id: string): Promise<EvaluationResultsResponse> => {
    return requestJson<EvaluationResultsResponse>(`/evaluations/${id}/results`);
  },

  submitCriterionFeedback: async (
    evaluationId: string,
    criterionId: string,
    body: CriterionFeedbackRequest,
  ): Promise<CriterionFeedbackResponse> => {
    return requestJson<CriterionFeedbackResponse>(
      `/feedback/${evaluationId}/criteria/${encodeURIComponent(criterionId)}`,
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    );
  },
};
```

- [ ] **Step 3: Replace `useSubmitFeedback.ts` with a criterion-scoped hook**

Replace the full contents of `client/src/features/evaluation/hooks/useSubmitFeedback.ts`:

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { evaluationApi } from '../api/evaluation.api';
import type { CriterionFeedbackRequest } from '../types';

export function useSubmitCriterionFeedback(evaluationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      criterionId,
      body,
    }: {
      criterionId: string;
      body: CriterionFeedbackRequest;
    }) => evaluationApi.submitCriterionFeedback(evaluationId, criterionId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluation-results', evaluationId] });
    },
  });
}
```

- [ ] **Step 4: Write a test for the hook**

Create `client/src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSubmitCriterionFeedback } from '../useSubmitFeedback';
import { evaluationApi } from '../../api/evaluation.api';

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    submitCriterionFeedback: vi.fn(),
  },
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useSubmitCriterionFeedback', () => {
  beforeEach(() => {
    vi.mocked(evaluationApi.submitCriterionFeedback).mockReset();
  });

  it('calls submitCriterionFeedback with the evaluation id, criterion id, and body', async () => {
    vi.mocked(evaluationApi.submitCriterionFeedback).mockResolvedValue({
      log_id: '1',
      evaluation_id: 'eval-1',
      user_id: 'user-1',
      agent_name: 'itso',
      criterion_id: 'itso-03',
      action: 'ACCEPT',
      edited_json: null,
      notes: null,
      created_at: '2026-08-10T00:00:00Z',
    });

    const { result } = renderHook(() => useSubmitCriterionFeedback('eval-1'), { wrapper });

    result.current.mutate({
      criterionId: 'itso-03',
      body: { agent_name: 'itso', action: 'ACCEPT' },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledWith(
      'eval-1',
      'itso-03',
      { agent_name: 'itso', action: 'ACCEPT' },
    );
  });
});
```

Note: rename this test file's extension to `.tsx` (`useSubmitFeedback.test.tsx`) since it contains JSX in the `wrapper` function — `.ts` files cannot contain JSX syntax under this project's TypeScript config.

- [ ] **Step 5: Run the test**

Run: `cd client && pnpm vitest run src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.tsx`
Expected: PASS

- [ ] **Step 6: Lint and typecheck**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors (the `pnpm build` step runs `tsc`, which will catch any type mismatches introduced here)

- [ ] **Step 7: Commit**

```bash
git add client/src/features/evaluation/types.ts client/src/features/evaluation/api/evaluation.api.ts client/src/features/evaluation/hooks/useSubmitFeedback.ts client/src/features/evaluation/hooks/__tests__/useSubmitFeedback.test.tsx
git commit -m "feat(evaluation): add criterion-scoped feedback API client and hook"
```

---

### Task 6: Accept/Reject/Edit controls on ITSO's Scorecard rows

**Files:**
- Create: `client/src/features/evaluation/components/CriterionFeedbackControls.tsx`
- Modify: `client/src/features/evaluation/components/Scorecard.tsx`

**Interfaces:**
- Consumes: `useSubmitCriterionFeedback` from Task 5. `CriterionScoreItem` (existing, `types.ts`).
- Produces: `<CriterionFeedbackControls>` component — used only inside `Scorecard.tsx` in this task; no later task depends on it.

- [ ] **Step 1: Create the controls component**

Create `client/src/features/evaluation/components/CriterionFeedbackControls.tsx`:

```tsx
import { useState } from 'react';
import { Check, X, Pencil } from 'lucide-react';
import { useSubmitCriterionFeedback } from '../hooks/useSubmitFeedback';
import type { CriterionScoreItem } from '../types';

type CriterionFeedbackControlsProps = {
  readonly evaluationId: string;
  readonly criterion: CriterionScoreItem;
};

export function CriterionFeedbackControls({
  evaluationId,
  criterion,
}: CriterionFeedbackControlsProps) {
  const [mode, setMode] = useState<'idle' | 'editing'>('idle');
  const [score, setScore] = useState(criterion.score);
  const [justification, setJustification] = useState(criterion.justification);
  const [submittedAction, setSubmittedAction] = useState<
    'ACCEPT' | 'REJECT' | 'EDIT' | null
  >(null);
  const mutation = useSubmitCriterionFeedback(evaluationId);

  function submit(
    action: 'ACCEPT' | 'REJECT' | 'EDIT',
    body: { score?: number; justification?: string } = {},
  ) {
    mutation.mutate(
      {
        criterionId: criterion.criterion_id,
        body: { agent_name: 'itso', action, ...body },
      },
      { onSuccess: () => setSubmittedAction(action) },
    );
    setMode('idle');
  }

  if (submittedAction) {
    return (
      <span className="inline-flex items-center rounded-sm border border-slate-200 bg-slate-50 px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-slate-500">
        {submittedAction === 'ACCEPT'
          ? 'Accepted'
          : submittedAction === 'REJECT'
            ? 'Rejected'
            : 'Edited'}
      </span>
    );
  }

  if (mode === 'editing') {
    return (
      <div className="grid gap-2 rounded-sm border border-slate-200 bg-white p-2">
        <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Corrected score
          <select
            className="mt-1 block w-full rounded-sm border border-slate-200 px-2 py-1 text-xs"
            value={score}
            onChange={(event) => setScore(Number(event.target.value))}
          >
            {[1, 2, 3, 4].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Corrected justification
          <textarea
            className="mt-1 block w-full rounded-sm border border-slate-200 px-2 py-1 text-xs"
            rows={3}
            value={justification}
            onChange={(event) => setJustification(event.target.value)}
          />
        </label>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[#1b3b87]"
            onClick={() => submit('EDIT', { score, justification })}
            disabled={!justification.trim()}
          >
            Save correction
          </button>
          <button
            type="button"
            className="rounded-sm border border-slate-200 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-500"
            onClick={() => setMode('idle')}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-1.5">
      <button
        type="button"
        title="Accept"
        className="inline-flex size-6 items-center justify-center rounded-sm border border-[#3b963e]/30 text-[#3b963e] hover:bg-[#3b963e]/10"
        onClick={() => submit('ACCEPT')}
        disabled={mutation.isPending}
      >
        <Check className="size-3.5" />
      </button>
      <button
        type="button"
        title="Reject"
        className="inline-flex size-6 items-center justify-center rounded-sm border border-[#b91c1c]/30 text-[#b91c1c] hover:bg-[#b91c1c]/10"
        onClick={() => submit('REJECT')}
        disabled={mutation.isPending}
      >
        <X className="size-3.5" />
      </button>
      <button
        type="button"
        title="Edit"
        className="inline-flex size-6 items-center justify-center rounded-sm border border-slate-300 text-slate-500 hover:bg-slate-50"
        onClick={() => setMode('editing')}
        disabled={mutation.isPending}
      >
        <Pencil className="size-3.5" />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Wire it into the Scorecard's criteria table**

In `client/src/features/evaluation/components/Scorecard.tsx`:

1. Add the import near the top, with the other component imports: `import { CriterionFeedbackControls } from './CriterionFeedbackControls';`
2. Add a 4th `<th>` to the table header (after the existing "Status" `<th>`, around line 306-309):

```tsx
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-slate-500 w-[9rem]">
                      Reviewer
                    </th>
```

3. Add a matching 4th `<td>` to the "Domain Group Header Row" (around line 340-359, after the existing Status `<td>`) — leave it empty for the header row:

```tsx
                          <td className="py-3 px-4 w-[9rem] border-t border-slate-200" />
```

4. Add a matching 4th `<td>` to the criterion detail row (around line 373-399, after the existing Status `<td>`), rendering the controls only for ITSO:

```tsx
                              <td className="py-4 px-4 align-top w-[9rem]">
                                {domain === 'itso' && evaluation && (
                                  <CriterionFeedbackControls
                                    evaluationId={evaluation.evaluation_id}
                                    criterion={criterion}
                                  />
                                )}
                              </td>
```

5. Also add the same empty `<td colSpan>` adjustment is **not** needed for the "SKIPPED" row (it already uses `colSpan={3}` — bump it to `colSpan={4}` so it still spans the full width now that there are 4 columns):

Find `<td colSpan={3} className="py-4 px-4">` (around line 319) and change to `<td colSpan={4} className="py-4 px-4">`.

- [ ] **Step 3: Manually verify in the browser**

Run: `cd client && pnpm dev`, then navigate to a completed evaluation's Scorecard (`/scorecard/{id}` or wherever the route is mounted — check `client/src/app/router.tsx` for the exact path if unsure). Confirm:
- SME/Coordinator/GAD rows show no reviewer controls (4th column empty).
- ITSO rows show Accept/Reject/Edit icon buttons.
- Clicking Edit expands the inline form pre-filled with the AI's score/justification; Save posts and the row collapses to an "Edited" badge.
- Clicking Accept/Reject immediately posts and shows an "Accepted"/"Rejected" badge.
- Network tab shows `POST /api/v1/feedback/{evaluation_id}/criteria/{criterion_id}` with the expected body.

- [ ] **Step 4: Lint and typecheck**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add client/src/features/evaluation/components/CriterionFeedbackControls.tsx client/src/features/evaluation/components/Scorecard.tsx
git commit -m "feat(evaluation): add Accept/Reject/Edit controls to ITSO scorecard rows"
```

---

### Task 7: DPO pair export script

**Files:**
- Create: `server/scripts/__init__.py` (if `server/scripts/` doesn't already exist)
- Create: `server/scripts/export_dpo_pairs.py`
- Test: `server/tests/scripts/test_export_dpo_pairs.py` (new, plus `server/tests/scripts/__init__.py`)

**Interfaces:**
- Consumes: `PreferenceLog.agent_name`/`criterion_id`/`edited_json` (Task 1), `AgentResult.prompt_text` (Task 2), `CriterionScore` (existing, `server/modules/synthesis/models.py`).
- Produces: a JSONL file — this is the final deliverable of this plan; no later task consumes its output programmatically (a human hands it to the offline training script described in the design doc, out of scope here).

- [ ] **Step 1: Check whether `server/scripts/` exists**

Run: `ls server/scripts 2>/dev/null || echo "does not exist"`. If it doesn't exist, create `server/scripts/__init__.py` as an empty file.

- [ ] **Step 2: Write the failing test**

Create `server/tests/scripts/__init__.py` (empty) and `server/tests/scripts/test_export_dpo_pairs.py`:

```python
"""DPO pair export: builds (prompt, chosen, rejected) triples from EDIT feedback."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.service import create_criterion_feedback
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.scripts.export_dpo_pairs import export_dpo_pairs


def _seed_evaluation(db_session, *, user_id):
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()
    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name="itso",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="ok",
        success=True,
        prompt_text='{"agent": "itso", "document_chunks": []}',
    )
    db_session.add(agent_result)
    db_session.flush()

    score_row = CriterionScore(
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        criterion_id="itso-03",
        criterion_title="Citation integrity",
        score=3,
        justification="Bibliography section found with 5 entries.",
    )
    db_session.add(score_row)
    db_session.commit()
    return job


def test_export_builds_pair_from_edit_action(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        score=2,
        justification="Bibliography entries are not APA-formatted.",
    )

    pairs = list(export_dpo_pairs(db_session))

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair["prompt"] == '{"agent": "itso", "document_chunks": []}'
    assert json.loads(pair["chosen"]) == {
        "score": 2,
        "justification": "Bibliography entries are not APA-formatted.",
    }
    assert json.loads(pair["rejected"]) == {
        "score": 3,
        "justification": "Bibliography section found with 5 entries.",
    }


def test_export_skips_accept_and_reject_actions(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="ACCEPT",
        user_id=admin_user.user_id,
    )

    pairs = list(export_dpo_pairs(db_session))
    assert pairs == []


def test_export_skips_rows_missing_prompt_snapshot(db_session, admin_user, caplog):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # Simulate an AgentResult saved before Task 2 shipped (no prompt_text).
    db_session.query(AgentResult).filter_by(evaluation_id=job.evaluation_id).update(
        {"prompt_text": None}
    )
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        score=2,
        justification="corrected",
    )

    pairs = list(export_dpo_pairs(db_session))
    assert pairs == []
    assert "no prompt_text snapshot" in caplog.text
```

Note: reuses the `admin_user` fixture from `server/tests/admin/conftest.py`. Add `server/tests/scripts/conftest.py` importing it if pytest doesn't already discover it across directories:

```python
"""Re-export shared fixtures for scripts tests."""

from __future__ import annotations

from server.tests.admin.conftest import admin_user  # noqa: F401
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/scripts -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.scripts.export_dpo_pairs'`

- [ ] **Step 4: Write the export script**

Create `server/scripts/export_dpo_pairs.py`:

```python
"""Export DPO training pairs from ITSO reviewer EDIT feedback.

Reads PreferenceLog EDIT rows for agent_name="itso", pairs each with the
prompt snapshot and original score/justification captured on AgentResult /
CriterionScore at scoring time, and yields one dict per pair:

    {"prompt": <str>, "chosen": <json str>, "rejected": <json str>}

Rows whose AgentResult has no prompt_text (e.g. persisted before this
feature shipped) are logged and skipped, never silently dropped.

Training itself is out of scope here — this script only produces the
JSONL a separate, manually-run LoRA DPO training script consumes. See
docs/superpowers/specs/2026-08-10-dpo-itso-scoring-design.md.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore

logger = logging.getLogger(__name__)


def export_dpo_pairs(db: Any) -> Iterator[dict[str, str]]:
    """Yield one DPO pair dict per usable EDIT row, latest edit per grain."""

    edit_rows = (
        db.query(PreferenceLog)
        .filter(PreferenceLog.agent_name == "itso", PreferenceLog.action == "EDIT")
        .order_by(PreferenceLog.created_at.desc())
        .all()
    )

    seen: set[tuple[Any, str]] = set()
    for log in edit_rows:
        grain = (log.evaluation_id, log.criterion_id)
        if grain in seen:
            continue
        seen.add(grain)

        agent_result = (
            db.query(AgentResult)
            .filter(
                AgentResult.evaluation_id == log.evaluation_id,
                AgentResult.agent_name == "itso",
            )
            .first()
        )
        if agent_result is None or not agent_result.prompt_text:
            logger.warning(
                "Skipping preference log %s: no prompt_text snapshot for "
                "evaluation %s (agent_result missing or predates prompt "
                "snapshotting).",
                log.log_id,
                log.evaluation_id,
            )
            continue

        original_score = (
            db.query(CriterionScore)
            .filter(
                CriterionScore.agent_result_id == agent_result.agent_result_id,
                CriterionScore.criterion_id == log.criterion_id,
            )
            .first()
        )
        if original_score is None:
            logger.warning(
                "Skipping preference log %s: no original CriterionScore row "
                "for criterion %s.",
                log.log_id,
                log.criterion_id,
            )
            continue

        if not log.edited_json:
            logger.warning(
                "Skipping preference log %s: EDIT action with empty edited_json.",
                log.log_id,
            )
            continue

        yield {
            "prompt": agent_result.prompt_text,
            "chosen": json.dumps(log.edited_json, ensure_ascii=False),
            "rejected": json.dumps(
                {
                    "score": original_score.score,
                    "justification": original_score.justification,
                },
                ensure_ascii=False,
            ),
        }


def main() -> None:
    import argparse

    from server.core.database import get_session_factory

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", help="Path to write the JSONL export to, e.g. itso_dpo_pairs.jsonl"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        count = 0
        with open(args.output, "w", encoding="utf-8") as f:
            for pair in export_dpo_pairs(session):
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                count += 1
        logger.info("Wrote %d DPO pairs to %s", count, args.output)
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/scripts -v`
Expected: PASS

- [ ] **Step 6: Lint**

Run: `uv run --project server ruff check server/scripts server/tests/scripts`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add server/scripts/__init__.py server/scripts/export_dpo_pairs.py server/tests/scripts/__init__.py server/tests/scripts/conftest.py server/tests/scripts/test_export_dpo_pairs.py
git commit -m "feat(scripts): add ITSO DPO pair export from reviewer EDIT feedback"
```

---

### Task 8: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `uv run --project server pytest`
Expected: PASS (no regressions in any other module)

- [ ] **Step 2: Run the full backend lint**

Run: `uv run --project server ruff check server`
Expected: no errors

- [ ] **Step 3: Run the full frontend build**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors

- [ ] **Step 4: Confirm the alembic chain is linear and applies cleanly**

Run: `uv run --project server alembic -c server/alembic.ini heads` — expect exactly one head (`20260810_0002`, or whatever followed it if task order differed). Then run `uv run --project server alembic -c server/alembic.ini upgrade head` against a scratch database to confirm both migrations apply without error.

- [ ] **Step 5: Manually export a sample and eyeball it**

With at least one EDIT submitted via the UI in Task 6's manual test, run:
`uv run --project server python -m server.scripts.export_dpo_pairs /tmp/itso_dpo_pairs.jsonl`
and open the file to confirm the `prompt`/`chosen`/`rejected` shape looks sane.
