# Curriculum Alignment Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new, independent curriculum-alignment-check pipeline that compares an uploaded SLM against a course's I/E/D curriculum map, fully decoupled from the existing SME/Coordinator/GAD/ITSO scoring pipeline.

**Architecture:** New backend module `server/modules/curriculum_map/` (models, pure comparison logic, an independent single-call LLM check, service, router) backed by 4 new Postgres tables. New frontend feature `client/src/features/curriculumAlignment/` with its own route, reusing existing design conventions (Tailwind classes, combobox pattern, table/badge/evidence-box styles) with no shared UI library changes.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + pytest (backend); React 18 + TanStack Router/Query + Tailwind v4 + vitest (frontend).

## Global Constraints

- Do not modify `server/modules/agents/scoring/curriculum_alignment.py`, `coordinator.py`, `sme.py`, `gad.py`, `itso.py`, or `supervisor.py` — this pipeline is fully independent (spec §2, §9).
- Backend: ruff-enforced (E, F, I, UP), line length 88, Python 3.12. Per-module layout: `router.py`, `service.py`, `models.py`, `schemas.py`, `exceptions.py`.
- Frontend: TypeScript, ESLint, Prettier. Features must stay self-contained and must not import from one another (`client/src/features/curriculumAlignment` must not import from `client/src/features/evaluation`).
- No numeric/banded score for this pipeline — output is descriptive only (spec §6).
- Blank curriculum-map cells are never evaluated, never flagged (spec §5).
- One LLM call per alignment-check run for the whole set of mapped objectives, never one call per objective (spec §5, [[llm-budget-and-multi-agent]]).
- Trigger is a separate, on-demand action — not part of `supervisor.py`'s automatic parallel dispatch (spec §5).
- Seeding is a one-time script against a JSON file, IT program only, no admin CRUD UI (spec §4, §9).
- Course selection is manual only — no AI/fuzzy course detection (spec §9).
- Run commands from repo root: `uv run --project server pytest ...` (backend), `cd client && pnpm test` (frontend, use `run` not watch mode for CI-style single runs — the `test` script already runs once).

---

## File Structure

**Backend — new module `server/modules/curriculum_map/`:**
- `__init__.py` — empty, package marker.
- `models.py` — `Course`, `CurriculumObjective`, `CurriculumMapCell`, `CurriculumAlignmentCheck` SQLAlchemy models.
- `comparison.py` — pure `compare_objective()` status logic (match/under-developed/over-developed/not_addressed).
- `document_text.py` — `extract_document_pages()` (fitz-based, mirrors `engine_scoring.py`'s `_load_document_text` but per-page) and `find_evidence_page()` (pure substring search over pages).
- `alignment_check.py` — the single-call LLM prompt and `run_alignment_llm()`.
- `service.py` — `list_courses()`, `get_course_curriculum_map()`, `run_curriculum_alignment_check()`, `get_alignment_check()`, `get_document_pages_for_check()`.
- `schemas.py` — Pydantic request/response models.
- `exceptions.py` — `CourseNotFoundError`, `NoCurriculumMapError`, `AlignmentCheckNotFoundError`.
- `router.py` — FastAPI endpoints.

**Backend — other files touched:**
- `server/alembic/versions/20260730_0001_add_curriculum_map_tables.py` — new migration (down_revision `20260716_0001`, the current head).
- `server/db/metadata.py` — register `curriculum_map.models` in `import_model_modules()`.
- `server/main.py` — register `curriculum_map.router` in `MODULE_ROUTER_PATHS`.
- `server/data/curriculum_map/it_program.json` — seed data.
- `server/scripts/seed_curriculum_map.py` — one-time seed script (mirrors `server/scripts/seed_rubrics.py`).

**Backend — new tests:**
- `server/tests/curriculum_map/__init__.py`
- `server/tests/curriculum_map/test_comparison.py`
- `server/tests/curriculum_map/test_document_text.py`
- `server/tests/curriculum_map/test_alignment_check.py`
- `server/tests/curriculum_map/test_service.py`
- `server/tests/curriculum_map/test_router.py`
- `server/tests/curriculum_map/test_seed_script.py`

**Frontend — new feature `client/src/features/curriculumAlignment/`:**
- `types.ts` — TS types mirroring backend schemas.
- `api/curriculumAlignment.api.ts` — `listCourses`, `runAlignmentCheck`, `getAlignmentCheck`, `getDocumentPages`.
- `utils/alignmentHelpers.ts` — status → color/label mapping (single source of truth).
- `utils/__tests__/alignmentHelpers.test.ts`
- `components/CourseSelector.tsx` — combobox, adapted from `shared/components/ProgramSelector.tsx`.
- `components/AlignmentResultsTable.tsx` — results table.
- `components/SlmReadingPane.tsx` — page-by-page reading pane with click-to-scroll-and-flash.
- `hooks/useCourses.ts`, `hooks/useRunAlignmentCheck.ts`, `hooks/useAlignmentCheck.ts`, `hooks/useDocumentPages.ts`.
- `pages/AlignmentCheckPage.tsx` — page composition.

**Frontend — other files touched:**
- `client/src/app/router.tsx` — add `alignmentRoute` at path `alignment`.
- `client/src/app/layout/Sidebar.tsx` — add nav entry to `workspaceNavItems`.

---

### Task 1: Alembic migration for the 4 new tables

**Files:**
- Create: `server/alembic/versions/20260730_0001_add_curriculum_map_tables.py`
- Test: `server/tests/curriculum_map/__init__.py`, `server/tests/curriculum_map/test_seed_script.py` (step 2 below only checks migration via model creation in Task 2 — this task just writes the migration file itself, verified by `alembic upgrade`/`downgrade` round-trip against a throwaway sqlite-incompatible check is skipped since the project uses Postgres in prod and sqlite in tests via `Base.metadata.create_all`; this migration is verified structurally in Task 2's test using the ORM models it backs).

**Interfaces:**
- Produces: tables `courses`, `curriculum_objectives`, `curriculum_map_cells`, `curriculum_alignment_checks` with the exact column names used by `models.py` in Task 2.

- [ ] **Step 1: Write the migration file**

```python
"""add curriculum map tables (courses, objectives, map cells, checks)

Revision ID: 20260730_0001
Revises: 20260716_0001
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260730_0001"
down_revision = "20260716_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "courses",
        sa.Column("course_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("course_code", sa.String(length=50), nullable=False),
        sa.Column("course_title", sa.String(length=300), nullable=False),
        sa.Column("program", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("course_code", name="uq_courses_course_code"),
    )

    op.create_table(
        "curriculum_objectives",
        sa.Column("objective_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("program", sa.String(length=50), nullable=False),
        sa.UniqueConstraint(
            "code", "program", name="uq_curriculum_objectives_code_program"
        ),
    )

    op.create_table(
        "curriculum_map_cells",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("objective_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=1), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.course_id"]),
        sa.ForeignKeyConstraint(
            ["objective_id"], ["curriculum_objectives.objective_id"]
        ),
        sa.UniqueConstraint(
            "course_id", "objective_id", name="uq_curriculum_map_cells_course_objective"
        ),
        sa.CheckConstraint("level IN ('I', 'E', 'D')", name="ck_curriculum_map_cells_level"),
    )

    op.create_table(
        "curriculum_alignment_checks",
        sa.Column("check_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("objective_results", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.course_id"]),
    )


def downgrade():
    op.drop_table("curriculum_alignment_checks")
    op.drop_table("curriculum_map_cells")
    op.drop_table("curriculum_objectives")
    op.drop_table("courses")
```

- [ ] **Step 2: Create the empty test package marker**

```python
# server/tests/curriculum_map/__init__.py
```
(empty file — mirrors every other `tests/<module>/__init__.py`)

- [ ] **Step 3: Commit**

```bash
git add server/alembic/versions/20260730_0001_add_curriculum_map_tables.py server/tests/curriculum_map/__init__.py
git commit -m "feat(curriculum-map): add migration for courses/objectives/map cells/checks tables"
```

---

### Task 2: SQLAlchemy models

**Files:**
- Create: `server/modules/curriculum_map/__init__.py` (empty), `server/modules/curriculum_map/models.py`
- Modify: `server/db/metadata.py`
- Test: `server/tests/curriculum_map/test_models.py`

**Interfaces:**
- Consumes: `server.core.database.Base` (`Mapped`/`mapped_column` declarative pattern, exactly as in `server/modules/rubrics/models.py`).
- Produces: `Course` (`course_id`, `course_code`, `course_title`, `program`), `CurriculumObjective` (`objective_id`, `code`, `description`, `program`), `CurriculumMapCell` (`id`, `course_id`, `objective_id`, `level`), `CurriculumAlignmentCheck` (`check_id`, `document_id`, `course_id`, `run_at`, `model_name`, `objective_results`, `summary`, `success`, `error_message`) — all imported by every later task in this plan.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/curriculum_map/test_models.py
"""Model-level tests: the ORM models match the migration's table shape."""

from __future__ import annotations

import uuid

from server.modules.curriculum_map.models import (
    Course,
    CurriculumAlignmentCheck,
    CurriculumMapCell,
    CurriculumObjective,
)
from server.modules.documents.models import Document


def test_can_insert_course_objective_and_cell(db_session) -> None:
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    db_session.add(course)
    db_session.flush()

    objective = CurriculumObjective(code="IT08", description="Teamwork", program="BSIT")
    db_session.add(objective)
    db_session.flush()

    cell = CurriculumMapCell(
        course_id=course.course_id, objective_id=objective.objective_id, level="D"
    )
    db_session.add(cell)
    db_session.commit()

    fetched = db_session.get(CurriculumMapCell, cell.id)
    assert fetched is not None
    assert fetched.level == "D"
    assert fetched.course_id == course.course_id


def test_blank_mapping_is_absence_of_a_row(db_session) -> None:
    course = Course(course_code="IT302", course_title="Networking", program="BSIT")
    db_session.add(course)
    db_session.commit()

    cells = (
        db_session.query(CurriculumMapCell)
        .filter(CurriculumMapCell.course_id == course.course_id)
        .all()
    )
    assert cells == []


def test_can_insert_alignment_check(db_session) -> None:
    course = Course(course_code="IT303", course_title="Algorithms", program="BSIT")
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/sample.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add_all([course, document])
    db_session.flush()

    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        model_name="test-model",
        objective_results=[{"code": "IT08", "status": "match"}],
        summary={"match": 1},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    fetched = db_session.get(CurriculumAlignmentCheck, check.check_id)
    assert fetched is not None
    assert fetched.objective_results == [{"code": "IT08", "status": "match"}]
    assert fetched.summary == {"match": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/curriculum_map/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.curriculum_map'`

- [ ] **Step 3: Write the models**

```python
# server/modules/curriculum_map/__init__.py
```
(empty file)

```python
# server/modules/curriculum_map/models.py
"""SQLAlchemy models for the curriculum alignment pipeline.

Structured tabular data (exact I/E/D cells), stored relationally like the
``rubrics`` module -- not embedded/retrieved from Chroma. A blank mapping
cell is the absence of a row in ``curriculum_map_cells``, not a stored null.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from server.core.database import Base
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("course_code", name="uq_courses_course_code"),)

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_code: Mapped[str] = mapped_column(String(50), nullable=False)
    course_title: Mapped[str] = mapped_column(String(300), nullable=False)
    program: Mapped[str] = mapped_column(String(50), nullable=False)


class CurriculumObjective(Base):
    __tablename__ = "curriculum_objectives"
    __table_args__ = (
        UniqueConstraint(
            "code", "program", name="uq_curriculum_objectives_code_program"
        ),
    )

    objective_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    program: Mapped[str] = mapped_column(String(50), nullable=False)


class CurriculumMapCell(Base):
    __tablename__ = "curriculum_map_cells"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "objective_id", name="uq_curriculum_map_cells_course_objective"
        ),
        CheckConstraint("level IN ('I', 'E', 'D')", name="ck_curriculum_map_cells_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.course_id"), nullable=False
    )
    objective_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("curriculum_objectives.objective_id"),
        nullable=False,
    )
    level: Mapped[str] = mapped_column(String(1), nullable=False)


class CurriculumAlignmentCheck(Base):
    __tablename__ = "curriculum_alignment_checks"

    check_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.course_id"), nullable=False
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    objective_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "Course",
    "CurriculumObjective",
    "CurriculumMapCell",
    "CurriculumAlignmentCheck",
]
```

- [ ] **Step 4: Register the module in Alembic's metadata registry**

In `server/db/metadata.py`, add the import alongside the other module imports (alphabetical, after `admin`, before `documents`):

```python
    from server.modules.admin import models as _admin_models  # noqa: F401
    from server.modules.auth import models as _auth_models  # noqa: F401
    from server.modules.curriculum_map import models as _curriculum_map_models  # noqa: F401
    from server.modules.documents import models as _document_models  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/curriculum_map/test_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add server/modules/curriculum_map/__init__.py server/modules/curriculum_map/models.py server/db/metadata.py server/tests/curriculum_map/test_models.py
git commit -m "feat(curriculum-map): add SQLAlchemy models for courses/objectives/map cells/checks"
```

---

### Task 3: Pure comparison logic

**Files:**
- Create: `server/modules/curriculum_map/comparison.py`
- Test: `server/tests/curriculum_map/test_comparison.py`

**Interfaces:**
- Produces: `compare_objective(*, is_addressed: bool, observed_level: str | None, expected_level: str) -> str` returning one of `"match"`, `"under-developed"`, `"over-developed"`, `"not_addressed"`. Consumed by `service.py` (Task 6).

- [ ] **Step 1: Write the failing test**

```python
# server/tests/curriculum_map/test_comparison.py
"""Unit tests for the pure I/E/D comparison logic.

No LLM, no IO -- exercises every branch of the priority-ordered status
rule from the design spec (docs/superpowers/specs/2026-07-30-curriculum-
alignment-pipeline-design.md section 5): is_addressed is checked first and
overrides whatever observed_level accompanies it.
"""

from __future__ import annotations

import pytest

from server.modules.curriculum_map.comparison import compare_objective


def test_not_addressed_when_is_addressed_false() -> None:
    assert (
        compare_objective(is_addressed=False, observed_level=None, expected_level="D")
        == "not_addressed"
    )


def test_not_addressed_overrides_a_stray_observed_level() -> None:
    # is_addressed takes priority even if observed_level is non-null.
    assert (
        compare_objective(is_addressed=False, observed_level="D", expected_level="D")
        == "not_addressed"
    )


def test_match_when_levels_equal() -> None:
    assert (
        compare_objective(is_addressed=True, observed_level="E", expected_level="E")
        == "match"
    )


def test_under_developed_when_observed_shallower() -> None:
    assert (
        compare_objective(is_addressed=True, observed_level="I", expected_level="D")
        == "under-developed"
    )


def test_over_developed_when_observed_deeper() -> None:
    assert (
        compare_objective(is_addressed=True, observed_level="D", expected_level="I")
        == "over-developed"
    )


@pytest.mark.parametrize(
    "expected_level,weaker,stronger",
    [("D", "E", "D"), ("D", "I", "E"), ("E", "I", "D")],
)
def test_strictness_ordering_i_lt_e_lt_d(expected_level, weaker, stronger) -> None:
    # Sanity check the I < E < D ordering directly via compare_objective.
    assert (
        compare_objective(is_addressed=True, observed_level=weaker, expected_level=expected_level)
        != "over-developed"
    )
    assert (
        compare_objective(is_addressed=True, observed_level=stronger, expected_level=expected_level)
        != "under-developed"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/curriculum_map/test_comparison.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.curriculum_map.comparison'`

- [ ] **Step 3: Write the implementation**

```python
# server/modules/curriculum_map/comparison.py
"""Pure I/E/D comparison logic -- no LLM, no IO, fully unit-testable.

Mirrors the design spec's priority-ordered rule (design doc section 5):
``is_addressed`` is checked first and always wins over whatever
``observed_level`` the LLM returned, so a not-addressed objective never
carries a stray depth reading.
"""

from __future__ import annotations

_LEVEL_ORDER: dict[str, int] = {"I": 0, "E": 1, "D": 2}


def compare_objective(
    *, is_addressed: bool, observed_level: str | None, expected_level: str
) -> str:
    """Return one of ``match``, ``under-developed``, ``over-developed``,
    ``not_addressed`` for a single mapped objective.
    """
    if not is_addressed:
        return "not_addressed"

    observed_rank = _LEVEL_ORDER.get(observed_level or "", -1)
    expected_rank = _LEVEL_ORDER[expected_level]

    if observed_rank == expected_rank:
        return "match"
    if observed_rank < expected_rank:
        return "under-developed"
    return "over-developed"


__all__ = ["compare_objective"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/curriculum_map/test_comparison.py -v`
Expected: PASS (8 tests, including the 3 parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add server/modules/curriculum_map/comparison.py server/tests/curriculum_map/test_comparison.py
git commit -m "feat(curriculum-map): add pure I/E/D comparison logic"
```

---

### Task 4: Document text extraction and evidence-page location

**Files:**
- Create: `server/modules/curriculum_map/document_text.py`
- Test: `server/tests/curriculum_map/test_document_text.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `extract_document_pages(document_id: uuid.UUID) -> list[str]` (fitz-based, one entry per PDF page, mirrors `engine_scoring.py`'s `_load_document_text` fallback discipline but returns a list instead of a joined string) and `find_evidence_page(pages: list[str], quote: str) -> int | None` (1-indexed page number of the first page containing `quote` as a substring, or `None` if not found). Consumed by `service.py` (Task 6) and by `router.py`'s document-pages endpoint (Task 8).

- [ ] **Step 1: Write the failing test**

```python
# server/tests/curriculum_map/test_document_text.py
"""Unit tests for the pure evidence-page locator.

``extract_document_pages`` needs a real PDF + DB row to exercise fully, so
it is covered indirectly by the service-layer tests (Task 6) via monkeypatch.
This file covers ``find_evidence_page``, which is pure and fully
unit-testable in isolation.
"""

from __future__ import annotations

from server.modules.curriculum_map.document_text import find_evidence_page


def test_finds_page_containing_exact_quote() -> None:
    pages = ["Intro text.", "Students design a linked list from scratch.", "Summary."]
    assert find_evidence_page(pages, "design a linked list") == 2


def test_returns_none_when_quote_not_found() -> None:
    pages = ["Intro text.", "Body text."]
    assert find_evidence_page(pages, "nonexistent quote") is None


def test_returns_none_for_empty_quote() -> None:
    pages = ["Intro text."]
    assert find_evidence_page(pages, "") is None


def test_returns_first_matching_page_when_quote_repeats() -> None:
    pages = ["First mention of teamwork.", "Second mention of teamwork."]
    assert find_evidence_page(pages, "teamwork") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/curriculum_map/test_document_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.curriculum_map.document_text'`

- [ ] **Step 3: Write the implementation**

```python
# server/modules/curriculum_map/document_text.py
"""SLM clean-text extraction and evidence-page location.

``extract_document_pages`` mirrors ``engine_scoring.py``'s
``_load_document_text`` (same fitz-based clean PDF extraction so this
pipeline sees identical input to the SME engine -- never joined/overlapping
DB chunks), but returns one entry per page instead of a single joined
string, so evidence quotes can be located to a specific page number for the
frontend's click-to-scroll link.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_document_pages(document_id: uuid.UUID) -> list[str]:
    """Return the SLM's clean per-page text via PyMuPDF, or ``[]`` on failure."""
    try:
        import fitz  # PyMuPDF
        from server.core.database import get_session_factory
        from server.modules.documents.models import Document

        session = get_session_factory()()
        try:
            document = session.get(Document, document_id)
            file_path = getattr(document, "file_path", None) if document else None
        finally:
            session.close()

        if not file_path:
            return []
        path = Path(str(file_path))
        if not path.is_file():
            logger.warning("Curriculum alignment: PDF not found at %s", path)
            return []

        pages: list[str] = []
        with fitz.open(path) as pdf:
            for page in pdf:
                pages.append(page.get_text() or "")
        return pages
    except Exception as exc:
        logger.warning(
            "Curriculum alignment: clean PDF extraction failed: %s",
            str(exc)[:200],
        )
        return []


def find_evidence_page(pages: list[str], quote: str) -> int | None:
    """Return the 1-indexed page number of the first page containing ``quote``.

    Returns ``None`` if the quote is empty or not found on any page. Used
    both to ground an LLM's evidence claim (substring check) and to give
    the frontend a page number to jump to.
    """
    if not quote.strip():
        return None
    for index, page_text in enumerate(pages, start=1):
        if quote in page_text:
            return index
    return None


__all__ = ["extract_document_pages", "find_evidence_page"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/curriculum_map/test_document_text.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/curriculum_map/document_text.py server/tests/curriculum_map/test_document_text.py
git commit -m "feat(curriculum-map): add per-page SLM text extraction and evidence locator"
```

---

### Task 5: Single-call LLM alignment check

**Files:**
- Create: `server/modules/curriculum_map/alignment_check.py`
- Test: `server/tests/curriculum_map/test_alignment_check.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (takes a plain LLM `client` with a `.generate(prompt, *, temperature, max_new_tokens) -> str` method, same interface as `server.core.llm.LocalLLMClient` and every `agents/scoring/*.py` module).
- Produces: `run_alignment_llm(client, mapped_objectives: list[dict], slm_text: str) -> list[dict]`, where each mapped objective dict is `{"code": str, "description": str}` and each returned dict is `{"objective_code": str, "is_addressed": bool, "observed_level": str | None, "evidence": str | None}`. Only codes present in `mapped_objectives` are returned (hallucinated codes filtered). Consumed by `service.py` (Task 6).

- [ ] **Step 1: Write the failing test**

```python
# server/tests/curriculum_map/test_alignment_check.py
"""Unit tests for the single-call curriculum-map LLM check.

Uses a fake client (same pattern as
tests/agents/test_curriculum_alignment.py) so no real LLM call happens.
"""

from __future__ import annotations

import json
from typing import Any

from server.modules.curriculum_map.alignment_check import run_alignment_llm


class FakeClient:
    def __init__(self, payload: dict[str, Any] | str) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def generate(self, prompt: str, **_: object) -> str:
        self.calls.append(prompt)
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


def test_happy_path_returns_all_objectives() -> None:
    client = FakeClient(
        {
            "results": [
                {
                    "objective_code": "IT08",
                    "is_addressed": True,
                    "observed_level": "I",
                    "evidence": "students work in pairs",
                }
            ]
        }
    )
    objectives = [{"code": "IT08", "description": "Teamwork"}]
    results = run_alignment_llm(client, objectives, "some SLM text")
    assert results == [
        {
            "objective_code": "IT08",
            "is_addressed": True,
            "observed_level": "I",
            "evidence": "students work in pairs",
        }
    ]
    assert len(client.calls) == 1


def test_hallucinated_objective_code_is_filtered() -> None:
    client = FakeClient(
        {
            "results": [
                {"objective_code": "IT08", "is_addressed": True, "observed_level": "E", "evidence": "x"},
                {"objective_code": "IT99", "is_addressed": True, "observed_level": "D", "evidence": "y"},
            ]
        }
    )
    objectives = [{"code": "IT08", "description": "Teamwork"}]
    results = run_alignment_llm(client, objectives, "text")
    assert [r["objective_code"] for r in results] == ["IT08"]


def test_malformed_json_returns_empty_list() -> None:
    client = FakeClient("not valid json")
    objectives = [{"code": "IT08", "description": "Teamwork"}]
    results = run_alignment_llm(client, objectives, "text")
    assert results == []


def test_empty_objectives_returns_empty_list_without_calling_llm() -> None:
    client = FakeClient({"results": []})
    results = run_alignment_llm(client, [], "text")
    assert results == []
    assert client.calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/curriculum_map/test_alignment_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.curriculum_map.alignment_check'`

- [ ] **Step 3: Write the implementation**

```python
# server/modules/curriculum_map/alignment_check.py
"""Single-call LLM check: is each mapped curriculum objective addressed by
the SLM, and at what observed I/E/D depth?

One call for the whole set of mapped objectives per run -- never one call
per objective (shared token/minute budget across SME/Coordinator/GAD/ITSO).
Independent of SME's objective extraction: this pipeline reads the SLM
content fresh rather than reusing any prior agent's extracted objectives.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

PROMPT = """You are checking a Self-Paced Learning Module (SLM) against a
list of curriculum objectives it is expected to address.

Your job is to extract facts only. Do NOT assign any score or I/E/D label
yourself except for the observed depth described below.

For EACH objective below, decide:
1. is_addressed: does the SLM content address this objective at all? Use
   this STRICT rule: the SLM must directly cover the same knowledge/skill
   named in the objective (matching topic and intent). A generic or
   unrelated mention does NOT count. If unsure, mark is_addressed = false.
2. observed_level: if addressed, classify the DEPTH at which the SLM
   engages this objective, using the same three tiers as the curriculum
   map itself:
   - "I" (Introductory): the objective is merely introduced or mentioned.
   - "E" (Enabling): the SLM has students practice or apply it.
   - "D" (Demonstrative): the SLM requires students to independently
     demonstrate mastery of it (e.g. an assessed project, case study, or
     capstone-style task).
   If not addressed, observed_level must be null.
3. evidence: for every objective you mark is_addressed = true, quote the
   exact SLM text that supports it. If you cannot quote real content, mark
   is_addressed = false and evidence = null.

Return ONLY valid JSON in exactly this shape:
{{
  "results": [
    {{
      "objective_code": "IT08",
      "is_addressed": true,
      "observed_level": "I",
      "evidence": "exact quote or null"
    }}
  ]
}}

CURRICULUM OBJECTIVES FOR THIS COURSE:
{objectives}

SLM CONTENT:
{content}
"""


def run_alignment_llm(
    client: Any,
    mapped_objectives: list[dict[str, Any]],
    slm_text: str,
) -> list[dict[str, Any]]:
    """Return per-objective alignment facts, filtered to requested codes.

    Returns an empty list on any failure (bad JSON, LLM error, no mapped
    objectives) so the caller can short-circuit cleanly rather than
    crashing the whole check.
    """
    if not mapped_objectives:
        return []

    valid_codes = {obj["code"] for obj in mapped_objectives}
    try:
        raw = client.generate(
            PROMPT.format(
                objectives=json.dumps(mapped_objectives, ensure_ascii=False),
                content=slm_text,
            ),
            temperature=0.0,
            max_new_tokens=1800,
        )
        data = json.loads(raw)
        raw_results = list(data.get("results", []))
    except Exception as exc:
        logger.warning(
            "Curriculum alignment LLM check failed: %s",
            str(exc)[:200],
        )
        return []

    filtered: list[dict[str, Any]] = []
    for item in raw_results:
        code = item.get("objective_code")
        if code not in valid_codes:
            continue
        filtered.append(
            {
                "objective_code": code,
                "is_addressed": bool(item.get("is_addressed", False)),
                "observed_level": item.get("observed_level"),
                "evidence": item.get("evidence"),
            }
        )
    return filtered


__all__ = ["run_alignment_llm", "PROMPT"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/curriculum_map/test_alignment_check.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add server/modules/curriculum_map/alignment_check.py server/tests/curriculum_map/test_alignment_check.py
git commit -m "feat(curriculum-map): add single-call LLM alignment check"
```

---

### Task 6: Exceptions and service layer

**Files:**
- Create: `server/modules/curriculum_map/exceptions.py`, `server/modules/curriculum_map/service.py`
- Test: `server/tests/curriculum_map/test_service.py`

**Interfaces:**
- Consumes: `Course`, `CurriculumObjective`, `CurriculumMapCell`, `CurriculumAlignmentCheck` (Task 2); `compare_objective` (Task 3); `extract_document_pages`, `find_evidence_page` (Task 4); `run_alignment_llm` (Task 5).
- Produces: `CourseNotFoundError`, `NoCurriculumMapError`, `AlignmentCheckNotFoundError` (all subclass `Exception`); `list_courses(db) -> list[Course]`; `run_curriculum_alignment_check(*, document_id, course_id, db, llm_client=None) -> CurriculumAlignmentCheck`; `get_alignment_check(check_id, db) -> CurriculumAlignmentCheck`; `get_document_pages_for_check(check_id, db) -> list[str]`. Consumed by `router.py` (Task 8).

- [ ] **Step 1: Write the failing test**

```python
# server/tests/curriculum_map/test_service.py
"""Service-layer tests for the curriculum alignment check orchestration.

The LLM and PDF extraction are monkeypatched so these tests exercise only
the service's own orchestration logic (short-circuits, persistence,
grounding) against a real (in-memory sqlite) db_session.
"""

from __future__ import annotations

import uuid

import pytest

from server.modules.curriculum_map import service
from server.modules.curriculum_map.exceptions import (
    AlignmentCheckNotFoundError,
    CourseNotFoundError,
    NoCurriculumMapError,
)
from server.modules.curriculum_map.models import Course, CurriculumMapCell, CurriculumObjective
from server.modules.documents.models import Document


def _make_course_with_map(db_session) -> tuple[Course, CurriculumObjective]:
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    objective = CurriculumObjective(code="IT08", description="Teamwork", program="BSIT")
    db_session.add_all([course, objective])
    db_session.flush()
    cell = CurriculumMapCell(
        course_id=course.course_id, objective_id=objective.objective_id, level="D"
    )
    db_session.add(cell)
    db_session.commit()
    return course, objective


def _make_document(db_session) -> Document:
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/does-not-exist.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add(document)
    db_session.commit()
    return document


def test_list_courses_returns_seeded_courses(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    courses = service.list_courses(db_session)
    assert [c.course_id for c in courses] == [course.course_id]


def test_run_check_raises_when_course_not_found(db_session, monkeypatch) -> None:
    document = _make_document(db_session)
    with pytest.raises(CourseNotFoundError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=uuid.uuid4(),
            db=db_session,
        )


def test_run_check_raises_when_no_curriculum_map(db_session) -> None:
    course = Course(course_code="IT999", course_title="Unmapped", program="BSIT")
    db_session.add(course)
    db_session.commit()
    document = _make_document(db_session)

    with pytest.raises(NoCurriculumMapError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            db=db_session,
        )


def test_run_check_happy_path_persists_result(db_session, monkeypatch) -> None:
    course, objective = _make_course_with_map(db_session)
    document = _make_document(db_session)

    monkeypatch.setattr(
        service,
        "extract_document_pages",
        lambda document_id: ["Students demonstrate teamwork in a capstone project."],
    )

    class FakeClient:
        model = "fake-model"

        def generate(self, prompt: str, **_: object) -> str:
            return (
                '{"results": [{"objective_code": "IT08", "is_addressed": true, '
                '"observed_level": "D", "evidence": "Students demonstrate teamwork '
                'in a capstone project."}]}'
            )

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        db=db_session,
        llm_client=FakeClient(),
    )

    assert check.success is True
    assert check.model_name == "fake-model"
    assert check.summary == {
        "total_mapped_objectives": 1,
        "match": 1,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
    }
    assert len(check.objective_results) == 1
    result = check.objective_results[0]
    assert result["code"] == "IT08"
    assert result["status"] == "match"
    assert result["evidence_page"] == 1

    fetched = service.get_alignment_check(check.check_id, db_session)
    assert fetched.check_id == check.check_id


def test_get_alignment_check_raises_when_missing(db_session) -> None:
    with pytest.raises(AlignmentCheckNotFoundError):
        service.get_alignment_check(uuid.uuid4(), db_session)


def test_ungrounded_evidence_is_downgraded_to_not_addressed(db_session, monkeypatch) -> None:
    course, objective = _make_course_with_map(db_session)
    document = _make_document(db_session)

    monkeypatch.setattr(
        service, "extract_document_pages", lambda document_id: ["Unrelated page text."]
    )

    class FakeClient:
        model = "fake-model"

        def generate(self, prompt: str, **_: object) -> str:
            return (
                '{"results": [{"objective_code": "IT08", "is_addressed": true, '
                '"observed_level": "D", "evidence": "text that does not appear '
                'in the document"}]}'
            )

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        db=db_session,
        llm_client=FakeClient(),
    )

    result = check.objective_results[0]
    assert result["status"] == "not_addressed"
    assert result["evidence_page"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/curriculum_map/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.curriculum_map.service'`

- [ ] **Step 3: Write the exceptions**

```python
# server/modules/curriculum_map/exceptions.py
"""Domain exceptions for the curriculum alignment pipeline."""

from __future__ import annotations


class CourseNotFoundError(Exception):
    """Raised when the requested course does not exist."""


class NoCurriculumMapError(Exception):
    """Raised when a course has zero mapped curriculum objectives.

    Distinguishes "not supported yet" from "0 objectives, all fine" -- the
    caller must never silently report a clean result for an unmapped
    course (design spec section 7).
    """


class AlignmentCheckNotFoundError(Exception):
    """Raised when the requested alignment check does not exist."""


__all__ = ["CourseNotFoundError", "NoCurriculumMapError", "AlignmentCheckNotFoundError"]
```

- [ ] **Step 4: Write the service**

```python
# server/modules/curriculum_map/service.py
"""Orchestration for the curriculum alignment check pipeline.

Fully independent of the SME/Coordinator/GAD/ITSO scoring pipeline and of
supervisor.py's parallel dispatch -- this is a separate, on-demand action
(design spec sections 2, 5, 9).
"""

from __future__ import annotations

import uuid
from typing import Any

from server.core.llm import get_llm_client

from .comparison import compare_objective
from .document_text import extract_document_pages, find_evidence_page
from .alignment_check import run_alignment_llm
from .exceptions import (
    AlignmentCheckNotFoundError,
    CourseNotFoundError,
    NoCurriculumMapError,
)
from .models import Course, CurriculumAlignmentCheck, CurriculumMapCell, CurriculumObjective

# Safety cap on the joined SLM text sent to the LLM. Mirrors the same
# budget-guard discipline as agents/base.py's prompt packing (design spec
# section 7: "SLM text exceeds prompt context budget"), just simpler since
# this pipeline sends one document's full text rather than ranked chunks.
_MAX_SLM_TEXT_CHARS = 20000


def _cap_slm_text(text: str) -> str:
    if len(text) <= _MAX_SLM_TEXT_CHARS:
        return text
    return text[:_MAX_SLM_TEXT_CHARS].rstrip() + "\n\n[...truncated for length...]"


def list_courses(db: Any) -> list[Course]:
    return db.query(Course).order_by(Course.course_code).all()


def _get_course(course_id: uuid.UUID, db: Any) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError(f"Course {course_id} not found")
    return course


def _get_mapped_objectives(course_id: uuid.UUID, db: Any) -> list[dict[str, Any]]:
    """Rows for this course only -- blank cells are absent rows, so this
    query already excludes them by construction (design spec section 3).
    """
    rows = (
        db.query(CurriculumMapCell, CurriculumObjective)
        .join(
            CurriculumObjective,
            CurriculumMapCell.objective_id == CurriculumObjective.objective_id,
        )
        .filter(CurriculumMapCell.course_id == course_id)
        .all()
    )
    return [
        {
            "code": objective.code,
            "description": objective.description,
            "expected_level": cell.level,
        }
        for cell, objective in rows
    ]


def run_curriculum_alignment_check(
    *,
    document_id: uuid.UUID,
    course_id: uuid.UUID,
    db: Any,
    llm_client: Any | None = None,
) -> CurriculumAlignmentCheck:
    course = _get_course(course_id, db)
    mapped = _get_mapped_objectives(course.course_id, db)
    if not mapped:
        raise NoCurriculumMapError(
            f"No curriculum map seeded for course {course.course_code}"
        )

    pages = extract_document_pages(document_id)
    slm_text = _cap_slm_text("\n\n".join(pages))

    client = llm_client or get_llm_client()
    llm_results = run_alignment_llm(
        client,
        [{"code": m["code"], "description": m["description"]} for m in mapped],
        slm_text,
    )
    llm_by_code = {r["objective_code"]: r for r in llm_results}

    objective_results: list[dict[str, Any]] = []
    status_counts = {
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
    }
    for objective in mapped:
        code = objective["code"]
        llm_result = llm_by_code.get(code)
        is_addressed = bool(llm_result and llm_result.get("is_addressed"))
        observed_level = llm_result.get("observed_level") if llm_result else None
        evidence = llm_result.get("evidence") if llm_result else None

        evidence_page = None
        if is_addressed and evidence:
            evidence_page = find_evidence_page(pages, evidence)
            if evidence_page is None:
                # Evidence not grounded in the source text -- downgrade
                # rather than trust an ungrounded claim (design spec s.7).
                is_addressed = False
                observed_level = None
                evidence = None

        status = compare_objective(
            is_addressed=is_addressed,
            observed_level=observed_level,
            expected_level=objective["expected_level"],
        )
        status_counts[status.replace("-", "_")] += 1

        objective_results.append(
            {
                "code": code,
                "description": objective["description"],
                "expected_level": objective["expected_level"],
                "is_addressed": is_addressed,
                "observed_level": observed_level,
                "status": status,
                "evidence": evidence,
                "evidence_page": evidence_page,
            }
        )

    check = CurriculumAlignmentCheck(
        document_id=document_id,
        course_id=course.course_id,
        model_name=getattr(client, "model", None),
        objective_results=objective_results,
        summary={"total_mapped_objectives": len(mapped), **status_counts},
        success=True,
    )
    db.add(check)
    db.commit()
    return check


def get_alignment_check(check_id: uuid.UUID, db: Any) -> CurriculumAlignmentCheck:
    check = db.get(CurriculumAlignmentCheck, check_id)
    if check is None:
        raise AlignmentCheckNotFoundError(f"Alignment check {check_id} not found")
    return check


def get_document_pages_for_check(check_id: uuid.UUID, db: Any) -> list[str]:
    check = get_alignment_check(check_id, db)
    return extract_document_pages(check.document_id)


__all__ = [
    "list_courses",
    "run_curriculum_alignment_check",
    "get_alignment_check",
    "get_document_pages_for_check",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/curriculum_map/test_service.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add server/modules/curriculum_map/exceptions.py server/modules/curriculum_map/service.py server/tests/curriculum_map/test_service.py
git commit -m "feat(curriculum-map): add service orchestration with evidence grounding"
```

---

### Task 7: Pydantic schemas

**Files:**
- Create: `server/modules/curriculum_map/schemas.py`

**Interfaces:**
- Consumes: nothing (pure Pydantic models, structurally matching the dicts/ORM attributes produced by `service.py`, Task 6).
- Produces: `CourseResponse`, `CourseListResponse`, `ObjectiveResultResponse`, `AlignmentCheckSummary`, `AlignmentCheckResponse`, `RunAlignmentCheckRequest`, `DocumentPagesResponse`. Consumed by `router.py` (Task 8).

This task has no independent test — its Pydantic models are exercised end-to-end by Task 8's router tests (schema validation is enforced by FastAPI at request/response time). Writing an isolated schema test would just re-assert Pydantic's own field typing, which the framework already guarantees.

- [ ] **Step 1: Write the schemas**

```python
# server/modules/curriculum_map/schemas.py
"""Pydantic schemas for curriculum-map endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CourseResponse(BaseModel):
    course_id: UUID
    course_code: str
    course_title: str
    program: str


class CourseListResponse(BaseModel):
    items: list[CourseResponse]


class ObjectiveResultResponse(BaseModel):
    code: str
    description: str
    expected_level: str
    is_addressed: bool
    observed_level: str | None = None
    status: str
    evidence: str | None = None
    evidence_page: int | None = None


class AlignmentCheckSummary(BaseModel):
    total_mapped_objectives: int
    match: int
    under_developed: int
    over_developed: int
    not_addressed: int


class RunAlignmentCheckRequest(BaseModel):
    document_id: UUID
    course_id: UUID


class AlignmentCheckResponse(BaseModel):
    check_id: UUID
    document_id: UUID
    course_id: UUID
    course_title: str
    run_at: datetime
    model_name: str | None = None
    objective_results: list[ObjectiveResultResponse]
    summary: AlignmentCheckSummary
    success: bool
    error_message: str | None = None


class DocumentPageResponse(BaseModel):
    page_number: int
    text: str


class DocumentPagesResponse(BaseModel):
    pages: list[DocumentPageResponse] = Field(default_factory=list)


__all__ = [
    "CourseResponse",
    "CourseListResponse",
    "ObjectiveResultResponse",
    "AlignmentCheckSummary",
    "RunAlignmentCheckRequest",
    "AlignmentCheckResponse",
    "DocumentPageResponse",
    "DocumentPagesResponse",
]
```

- [ ] **Step 2: Commit**

```bash
git add server/modules/curriculum_map/schemas.py
git commit -m "feat(curriculum-map): add Pydantic request/response schemas"
```

---

### Task 8: Router and app registration

**Files:**
- Create: `server/modules/curriculum_map/router.py`
- Modify: `server/main.py`
- Test: `server/tests/curriculum_map/test_router.py`

**Interfaces:**
- Consumes: `service.py` (Task 6), `schemas.py` (Task 7), `require_authenticated_user`/`AuthenticatedUser` (`server.modules.auth.dependencies`/`server.modules.auth.service`, same as `documents/router.py`), `get_db_session` (`server.core.database`).
- Produces: `router` (`APIRouter`), registered under prefix `/curriculum-map`. Endpoints: `GET /curriculum-map/courses`, `POST /curriculum-map/checks`, `GET /curriculum-map/checks/{check_id}`, `GET /curriculum-map/checks/{check_id}/document-pages`.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/curriculum_map/test_router.py
"""Router tests using the shared TestClient fixture (server/tests/conftest.py)."""

from __future__ import annotations

import uuid

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.curriculum_map.models import Course, CurriculumMapCell, CurriculumObjective
from server.modules.documents.models import Document


def _login(client, db_session, email="faculty@example.com"):
    user = create_user(
        db_session, name="Faculty User", email=email, password="correct-horse-battery",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correct-horse-battery"}
    )
    assert response.status_code == 200
    return user


def test_list_courses_requires_auth(client) -> None:
    response = client.get("/api/v1/curriculum-map/courses")
    assert response.status_code == 401


def test_list_courses_returns_seeded_courses(client, db_session) -> None:
    _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    db_session.add(course)
    db_session.commit()

    response = client.get("/api/v1/curriculum-map/courses")
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["course_code"] == "IT301"


def test_run_check_returns_404_for_unknown_course(client, db_session) -> None:
    _login(client, db_session)
    document = Document(
        title="Sample SLM", source_type="slm", file_path="/tmp/x.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add(document)
    db_session.commit()

    response = client.post(
        "/api/v1/curriculum-map/checks",
        json={"document_id": str(document.document_id), "course_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_run_check_returns_422_for_unmapped_course(client, db_session) -> None:
    _login(client, db_session)
    course = Course(course_code="IT999", course_title="Unmapped", program="BSIT")
    document = Document(
        title="Sample SLM", source_type="slm", file_path="/tmp/x.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add_all([course, document])
    db_session.commit()

    response = client.post(
        "/api/v1/curriculum-map/checks",
        json={"document_id": str(document.document_id), "course_id": str(course.course_id)},
    )
    assert response.status_code == 422


def test_get_check_returns_404_for_unknown_id(client, db_session) -> None:
    _login(client, db_session)
    response = client.get(f"/api/v1/curriculum-map/checks/{uuid.uuid4()}")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/curriculum_map/test_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.modules.curriculum_map.router'`

- [ ] **Step 3: Write the router**

```python
# server/modules/curriculum_map/router.py
"""HTTP endpoints for the curriculum alignment check pipeline.

Separate, on-demand endpoints -- not part of the evaluation orchestrator's
automatic dispatch (design spec section 5).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser

from .exceptions import (
    AlignmentCheckNotFoundError,
    CourseNotFoundError,
    NoCurriculumMapError,
)
from .schemas import (
    AlignmentCheckResponse,
    CourseListResponse,
    CourseResponse,
    DocumentPageResponse,
    DocumentPagesResponse,
    RunAlignmentCheckRequest,
)
from .service import (
    get_alignment_check,
    get_document_pages_for_check,
    list_courses,
    run_curriculum_alignment_check,
)

router = APIRouter(prefix="/curriculum-map", tags=["curriculum-map"])


@router.get("/courses", response_model=CourseListResponse)
def list_courses_endpoint(
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> CourseListResponse:
    courses = list_courses(db)
    return CourseListResponse(
        items=[
            CourseResponse(
                course_id=c.course_id,
                course_code=c.course_code,
                course_title=c.course_title,
                program=c.program,
            )
            for c in courses
        ]
    )


@router.post("/checks", response_model=AlignmentCheckResponse, status_code=status.HTTP_201_CREATED)
def run_check_endpoint(
    body: RunAlignmentCheckRequest,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> AlignmentCheckResponse:
    try:
        check = run_curriculum_alignment_check(
            document_id=body.document_id, course_id=body.course_id, db=db
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NoCurriculumMapError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _to_response(check, db)


@router.get("/checks/{check_id}", response_model=AlignmentCheckResponse)
def get_check_endpoint(
    check_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> AlignmentCheckResponse:
    try:
        check = get_alignment_check(check_id, db)
    except AlignmentCheckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(check, db)


@router.get("/checks/{check_id}/document-pages", response_model=DocumentPagesResponse)
def get_document_pages_endpoint(
    check_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> DocumentPagesResponse:
    try:
        pages = get_document_pages_for_check(check_id, db)
    except AlignmentCheckNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentPagesResponse(
        pages=[
            DocumentPageResponse(page_number=i, text=text)
            for i, text in enumerate(pages, start=1)
        ]
    )


def _to_response(check: Any, db: Any) -> AlignmentCheckResponse:
    from .models import Course

    course = db.get(Course, check.course_id)
    return AlignmentCheckResponse(
        check_id=check.check_id,
        document_id=check.document_id,
        course_id=check.course_id,
        course_title=course.course_title if course else "",
        run_at=check.run_at,
        model_name=check.model_name,
        objective_results=check.objective_results,
        summary=check.summary,
        success=check.success,
        error_message=check.error_message,
    )


__all__ = ["router"]
```

- [ ] **Step 4: Register the router in `server/main.py`**

Add `"server.modules.curriculum_map.router"` to `MODULE_ROUTER_PATHS`:

```python
MODULE_ROUTER_PATHS = (
    "server.modules.documents.router",
    "server.modules.auth.router",
    "server.modules.synthesis.router",
    "server.modules.evaluations.router",
    "server.modules.feedback.router",
    "server.modules.admin.router",
    "server.modules.curriculum_map.router",
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/curriculum_map/test_router.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Run the full curriculum_map test suite**

Run: `uv run --project server pytest server/tests/curriculum_map/ -v`
Expected: PASS (all tests across every file in this task group)

- [ ] **Step 7: Run ruff on the new module**

Run: `uv run --project server ruff check server/modules/curriculum_map server/tests/curriculum_map`
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add server/modules/curriculum_map/router.py server/main.py server/tests/curriculum_map/test_router.py
git commit -m "feat(curriculum-map): add router and register it in the app"
```

---

### Task 9: Seed data and seed script

**Files:**
- Create: `server/data/curriculum_map/it_program.json`, `server/scripts/seed_curriculum_map.py`
- Test: `server/tests/curriculum_map/test_seed_script.py`

**Interfaces:**
- Consumes: `Course`, `CurriculumObjective`, `CurriculumMapCell` (Task 2).
- Produces: `seed_curriculum_map(db, data: dict) -> None` (importable function, called by the script's `__main__` block against a real session, and directly by the test against `db_session`).

- [ ] **Step 1: Write the failing test**

```python
# server/tests/curriculum_map/test_seed_script.py
"""Tests for the curriculum-map seed script against the bundled IT JSON."""

from __future__ import annotations

import json
from pathlib import Path

from server.modules.curriculum_map.models import Course, CurriculumMapCell, CurriculumObjective
from server.scripts.seed_curriculum_map import seed_curriculum_map

ROOT = Path(__file__).resolve().parents[2]
SEED_JSON = ROOT / "data" / "curriculum_map" / "it_program.json"


def test_seed_json_is_valid_and_loads() -> None:
    payload = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    assert payload["program"] == "BSIT"
    assert len(payload["courses"]) >= 1
    assert len(payload["objectives"]) >= 1


def test_seed_creates_courses_objectives_and_cells(db_session) -> None:
    payload = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    seed_curriculum_map(db_session, payload)

    courses = db_session.query(Course).all()
    objectives = db_session.query(CurriculumObjective).all()
    cells = db_session.query(CurriculumMapCell).all()

    assert len(courses) == len(payload["courses"])
    assert len(objectives) == len(payload["objectives"])
    expected_cell_count = sum(
        1
        for course in payload["courses"]
        for level in course["objective_levels"].values()
        if level
    )
    assert len(cells) == expected_cell_count


def test_seed_is_idempotent(db_session) -> None:
    payload = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    seed_curriculum_map(db_session, payload)
    seed_curriculum_map(db_session, payload)

    courses = db_session.query(Course).all()
    assert len(courses) == len(payload["courses"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --project server pytest server/tests/curriculum_map/test_seed_script.py -v`
Expected: FAIL with `FileNotFoundError` (JSON doesn't exist yet) or `ModuleNotFoundError`

- [ ] **Step 3: Write the seed JSON**

```json
{
  "program": "BSIT",
  "objectives": [
    { "code": "IT03", "description": "Apply knowledge of computing appropriate to the discipline." },
    { "code": "IT08", "description": "Function effectively as an individual and as a member or leader in diverse teams and in multidisciplinary settings." },
    { "code": "IT11", "description": "Understand the reasoning behind professional, ethical, legal, security, and social issues and responsibilities." }
  ],
  "courses": [
    {
      "course_code": "IT301",
      "course_title": "Data Structures and Algorithms",
      "objective_levels": { "IT03": "E", "IT08": "I", "IT11": "" }
    },
    {
      "course_code": "IT401",
      "course_title": "Capstone Project 1",
      "objective_levels": { "IT03": "D", "IT08": "D", "IT11": "D" }
    }
  ]
}
```

- [ ] **Step 4: Write the seed script**

```python
# server/scripts/seed_curriculum_map.py
"""One-time seed script for the curriculum alignment pipeline's IT program
data. Mirrors server/scripts/seed_rubrics.py's shape.

Usage (from repo root):
    uv run --project server python -m server.scripts.seed_curriculum_map
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.curriculum_map.models import (  # noqa: E402
    Course,
    CurriculumMapCell,
    CurriculumObjective,
)


def seed_curriculum_map(db: Any, payload: dict[str, Any]) -> None:
    """Idempotent seed: existing rows (matched by unique code) are left
    untouched; only missing courses/objectives/cells are inserted.
    """
    program = payload["program"]

    objectives_by_code: dict[str, CurriculumObjective] = {}
    for obj_data in payload["objectives"]:
        existing = (
            db.query(CurriculumObjective)
            .filter_by(code=obj_data["code"], program=program)
            .one_or_none()
        )
        if existing is None:
            existing = CurriculumObjective(
                code=obj_data["code"], description=obj_data["description"], program=program
            )
            db.add(existing)
            db.flush()
        objectives_by_code[obj_data["code"]] = existing

    for course_data in payload["courses"]:
        course = (
            db.query(Course)
            .filter_by(course_code=course_data["course_code"])
            .one_or_none()
        )
        if course is None:
            course = Course(
                course_code=course_data["course_code"],
                course_title=course_data["course_title"],
                program=program,
            )
            db.add(course)
            db.flush()

        for code, level in course_data["objective_levels"].items():
            if not level:
                continue  # blank cell: absence of a row, never inserted
            objective = objectives_by_code[code]
            existing_cell = (
                db.query(CurriculumMapCell)
                .filter_by(course_id=course.course_id, objective_id=objective.objective_id)
                .one_or_none()
            )
            if existing_cell is None:
                db.add(
                    CurriculumMapCell(
                        course_id=course.course_id,
                        objective_id=objective.objective_id,
                        level=level,
                    )
                )

    db.commit()


def main() -> None:
    from server.core.database import get_session_factory

    seed_path = ROOT / "data" / "curriculum_map" / "it_program.json"
    payload = json.loads(seed_path.read_text(encoding="utf-8"))

    session = get_session_factory()()
    try:
        seed_curriculum_map(session, payload)
        print(f"Seeded curriculum map for program {payload['program']}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()


__all__ = ["seed_curriculum_map", "main"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --project server pytest server/tests/curriculum_map/test_seed_script.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run ruff on the seed script**

Run: `uv run --project server ruff check server/scripts/seed_curriculum_map.py`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add server/data/curriculum_map/it_program.json server/scripts/seed_curriculum_map.py server/tests/curriculum_map/test_seed_script.py
git commit -m "feat(curriculum-map): add IT program seed data and idempotent seed script"
```

---

### Task 10: Frontend types and API client

**Files:**
- Create: `client/src/features/curriculumAlignment/types.ts`, `client/src/features/curriculumAlignment/api/curriculumAlignment.api.ts`

**Interfaces:**
- Consumes: `requestJson` (`@/shared/api/http`, same as `evaluation.api.ts`).
- Produces: types `Course`, `ObjectiveResult`, `AlignmentCheckSummary`, `AlignmentCheck`, `DocumentPage`; API object `curriculumAlignmentApi` with `listCourses()`, `runCheck(documentId, courseId)`, `getCheck(checkId)`, `getDocumentPages(checkId)`. Consumed by every hook in Tasks 11-13.

No isolated unit test for this task — it's a thin typed HTTP wrapper with no branching logic (mirrors `evaluation.api.ts`, which also has no dedicated test file); it's exercised indirectly through the hooks in later tasks.

- [ ] **Step 1: Write the types**

```typescript
// client/src/features/curriculumAlignment/types.ts
export interface Course {
  course_id: string;
  course_code: string;
  course_title: string;
  program: string;
}

export interface CourseListResponse {
  items: Course[];
}

export type AlignmentStatus = 'match' | 'under-developed' | 'over-developed' | 'not_addressed';

export interface ObjectiveResult {
  code: string;
  description: string;
  expected_level: 'I' | 'E' | 'D';
  is_addressed: boolean;
  observed_level: 'I' | 'E' | 'D' | null;
  status: AlignmentStatus;
  evidence: string | null;
  evidence_page: number | null;
}

export interface AlignmentCheckSummary {
  total_mapped_objectives: number;
  match: number;
  under_developed: number;
  over_developed: number;
  not_addressed: number;
}

export interface AlignmentCheck {
  check_id: string;
  document_id: string;
  course_id: string;
  course_title: string;
  run_at: string;
  model_name: string | null;
  objective_results: ObjectiveResult[];
  summary: AlignmentCheckSummary;
  success: boolean;
  error_message: string | null;
}

export interface DocumentPage {
  page_number: number;
  text: string;
}

export interface DocumentPagesResponse {
  pages: DocumentPage[];
}
```

- [ ] **Step 2: Write the API client**

```typescript
// client/src/features/curriculumAlignment/api/curriculumAlignment.api.ts
import { requestJson } from '@/shared/api/http';
import type {
  AlignmentCheck,
  CourseListResponse,
  DocumentPagesResponse,
} from '../types';

export const curriculumAlignmentApi = {
  listCourses: async (): Promise<CourseListResponse> => {
    return requestJson<CourseListResponse>('/curriculum-map/courses');
  },

  runCheck: async (documentId: string, courseId: string): Promise<AlignmentCheck> => {
    return requestJson<AlignmentCheck>('/curriculum-map/checks', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, course_id: courseId }),
    });
  },

  getCheck: async (checkId: string): Promise<AlignmentCheck> => {
    return requestJson<AlignmentCheck>(`/curriculum-map/checks/${checkId}`);
  },

  getDocumentPages: async (checkId: string): Promise<DocumentPagesResponse> => {
    return requestJson<DocumentPagesResponse>(`/curriculum-map/checks/${checkId}/document-pages`);
  },
};
```

- [ ] **Step 3: Commit**

```bash
git add client/src/features/curriculumAlignment/types.ts client/src/features/curriculumAlignment/api/curriculumAlignment.api.ts
git commit -m "feat(curriculum-alignment): add frontend types and API client"
```

---

### Task 11: Status color/label helper

**Files:**
- Create: `client/src/features/curriculumAlignment/utils/alignmentHelpers.ts`, `client/src/features/curriculumAlignment/utils/__tests__/alignmentHelpers.test.ts`

**Interfaces:**
- Consumes: `AlignmentStatus` (Task 10).
- Produces: `statusLabel(status: AlignmentStatus) -> string`, `statusBadgeClasses(status: AlignmentStatus) -> string` (Tailwind classes, graduated-severity palette per the approved design: match=green `#3b963e`, over-developed=light blue `#3eaed4`, under-developed=gold `#f2c811`, not_addressed=red `#b91c1c`). Consumed by `AlignmentResultsTable.tsx` (Task 14).

- [ ] **Step 1: Write the failing test**

```typescript
// client/src/features/curriculumAlignment/utils/__tests__/alignmentHelpers.test.ts
import { describe, expect, it } from 'vitest';
import { statusBadgeClasses, statusLabel } from '../alignmentHelpers';

describe('statusLabel', () => {
  it('renders a human label for each status', () => {
    expect(statusLabel('match')).toBe('Match');
    expect(statusLabel('under-developed')).toBe('Under-developed');
    expect(statusLabel('over-developed')).toBe('Over-developed');
    expect(statusLabel('not_addressed')).toBe('Not addressed');
  });
});

describe('statusBadgeClasses', () => {
  it('uses green for match', () => {
    expect(statusBadgeClasses('match')).toContain('#3b963e');
  });

  it('uses light blue for over-developed', () => {
    expect(statusBadgeClasses('over-developed')).toContain('#3eaed4');
  });

  it('uses gold for under-developed', () => {
    expect(statusBadgeClasses('under-developed')).toContain('#f2c811');
  });

  it('uses red for not_addressed', () => {
    expect(statusBadgeClasses('not_addressed')).toContain('#b91c1c');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd client && pnpm test -- alignmentHelpers`
Expected: FAIL — module `../alignmentHelpers` does not exist

- [ ] **Step 3: Write the implementation**

```typescript
// client/src/features/curriculumAlignment/utils/alignmentHelpers.ts
// Single source of truth for status -> label/color, mirroring the pattern
// evaluation/utils/scoreHelpers.ts uses for adjectival ratings (avoids the
// duplicated color logic Scorecard.tsx and MonitoringTable.tsx currently have).
import type { AlignmentStatus } from '../types';

const STATUS_LABELS: Record<AlignmentStatus, string> = {
  match: 'Match',
  'under-developed': 'Under-developed',
  'over-developed': 'Over-developed',
  not_addressed: 'Not addressed',
};

const STATUS_BADGE_CLASSES: Record<AlignmentStatus, string> = {
  match: 'border-[#3b963e]/30 bg-[#3b963e]/10 text-[#3b963e]',
  'over-developed': 'border-[#3eaed4]/30 bg-[#3eaed4]/10 text-[#3eaed4]',
  'under-developed': 'border-[#f2c811]/30 bg-[#f2c811]/10 text-[#8a6d00]',
  not_addressed: 'border-[#b91c1c]/30 bg-[#b91c1c]/10 text-[#b91c1c]',
};

export function statusLabel(status: AlignmentStatus): string {
  return STATUS_LABELS[status];
}

export function statusBadgeClasses(status: AlignmentStatus): string {
  return STATUS_BADGE_CLASSES[status];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd client && pnpm test -- alignmentHelpers`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add client/src/features/curriculumAlignment/utils/alignmentHelpers.ts client/src/features/curriculumAlignment/utils/__tests__/alignmentHelpers.test.ts
git commit -m "feat(curriculum-alignment): add status color/label helper"
```

---

### Task 12: React Query hooks

**Files:**
- Create: `client/src/features/curriculumAlignment/hooks/useCourses.ts`, `client/src/features/curriculumAlignment/hooks/useRunAlignmentCheck.ts`, `client/src/features/curriculumAlignment/hooks/useAlignmentCheck.ts`, `client/src/features/curriculumAlignment/hooks/useDocumentPages.ts`

**Interfaces:**
- Consumes: `curriculumAlignmentApi` (Task 10).
- Produces: `useCourses()` (React Query `useQuery`), `useRunAlignmentCheck()` (React Query `useMutation`), `useAlignmentCheck(checkId)` (`useQuery`), `useDocumentPages(checkId)` (`useQuery`). Consumed by `AlignmentCheckPage.tsx` (Task 15).

No isolated unit test — these are thin React Query wrappers with no branching logic, identical in shape to `useEvaluationStatus.ts`/`useEvaluationReport.ts`, neither of which has a dedicated test file in this codebase; they are exercised through the page in Task 15 (manual verification per the `run`/`verify` skills, since these are UI-integration concerns).

- [ ] **Step 1: Write `useCourses`**

```typescript
// client/src/features/curriculumAlignment/hooks/useCourses.ts
import { useQuery } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useCourses() {
  return useQuery({
    queryKey: ['curriculum-map', 'courses'],
    queryFn: () => curriculumAlignmentApi.listCourses(),
  });
}
```

- [ ] **Step 2: Write `useRunAlignmentCheck`**

```typescript
// client/src/features/curriculumAlignment/hooks/useRunAlignmentCheck.ts
import { useMutation } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useRunAlignmentCheck() {
  return useMutation({
    mutationFn: ({ documentId, courseId }: { documentId: string; courseId: string }) =>
      curriculumAlignmentApi.runCheck(documentId, courseId),
  });
}
```

- [ ] **Step 3: Write `useAlignmentCheck`**

```typescript
// client/src/features/curriculumAlignment/hooks/useAlignmentCheck.ts
import { useQuery } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useAlignmentCheck(checkId: string | null) {
  return useQuery({
    queryKey: ['curriculum-map', 'check', checkId],
    queryFn: () => curriculumAlignmentApi.getCheck(checkId as string),
    enabled: !!checkId,
  });
}
```

- [ ] **Step 4: Write `useDocumentPages`**

```typescript
// client/src/features/curriculumAlignment/hooks/useDocumentPages.ts
import { useQuery } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useDocumentPages(checkId: string | null) {
  return useQuery({
    queryKey: ['curriculum-map', 'document-pages', checkId],
    queryFn: () => curriculumAlignmentApi.getDocumentPages(checkId as string),
    enabled: !!checkId,
  });
}
```

- [ ] **Step 5: Type-check the new hooks**

Run: `cd client && pnpm build`
Expected: compiles with no new TypeScript errors (existing unrelated errors, if any, are out of scope for this task)

- [ ] **Step 6: Commit**

```bash
git add client/src/features/curriculumAlignment/hooks/useCourses.ts client/src/features/curriculumAlignment/hooks/useRunAlignmentCheck.ts client/src/features/curriculumAlignment/hooks/useAlignmentCheck.ts client/src/features/curriculumAlignment/hooks/useDocumentPages.ts
git commit -m "feat(curriculum-alignment): add React Query hooks"
```

---

### Task 13: CourseSelector component

**Files:**
- Create: `client/src/features/curriculumAlignment/components/CourseSelector.tsx`

**Interfaces:**
- Consumes: `Course` (Task 10), `cn` (`@/shared/components/utils`).
- Produces: `<CourseSelector value courses onChange label placeholder hint id required disabled />`. Consumed by `AlignmentCheckPage.tsx` (Task 15).

No isolated unit test — this is a direct structural adaptation of `ProgramSelector.tsx` (which itself has no dedicated test file in this codebase); its keyboard/ARIA behavior is inherited unchanged from a component already in production use, and it is exercised end-to-end when the page is manually verified (Task 16, `verify` skill).

- [ ] **Step 1: Write the component**

```typescript
// client/src/features/curriculumAlignment/components/CourseSelector.tsx
// Adapted from shared/components/ProgramSelector.tsx: same combobox
// mechanics (search, keyboard nav, ARIA), backed by courses instead of
// programs, with a flat (ungrouped) list since courses aren't organized
// into colleges the way programs are.
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import type { Course } from '../types';

type CourseSelectorProps = {
  value: string;
  onChange: (courseId: string) => void;
  courses: Course[];
  label?: string;
  placeholder?: string;
  hint?: string;
  id?: string;
  required?: boolean;
  disabled?: boolean;
};

export function CourseSelector({
  value,
  onChange,
  courses,
  label,
  placeholder = 'Select a course',
  hint,
  id: idProp,
  required,
  disabled,
}: CourseSelectorProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const listId = `${id}-list`;

  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const filteredCourses = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return courses;
    return courses.filter(
      (course) =>
        course.course_code.toLowerCase().includes(trimmed) ||
        course.course_title.toLowerCase().includes(trimmed),
    );
  }, [courses, query]);

  const selectedCourse = useMemo(
    () => courses.find((course) => course.course_id === value) ?? null,
    [courses, value],
  );

  const safeHighlightedIndex = Math.min(highlightedIndex, Math.max(0, filteredCourses.length - 1));

  const openPicker = () => {
    setIsOpen(true);
    setQuery('');
    const selectedIndex = courses.findIndex((course) => course.course_id === value);
    setHighlightedIndex(Math.max(0, selectedIndex));
    window.setTimeout(() => searchInputRef.current?.focus(), 0);
  };

  const closePicker = () => {
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!isOpen) return;
    const active = itemRefs.current[safeHighlightedIndex];
    active?.scrollIntoView({ block: 'nearest' });
  }, [isOpen, safeHighlightedIndex]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const handleSelect = (courseId: string) => {
    onChange(courseId);
    closePicker();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    const count = filteredCourses.length;
    if (count === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % count);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev - 1 + count) % count);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const course = filteredCourses[safeHighlightedIndex];
      if (course) handleSelect(course.course_id);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closePicker();
    }
  };

  const handleTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openPicker();
    }
  };

  return (
    <div ref={containerRef} className="relative min-w-0 w-full">
      {label ? (
        <label
          htmlFor={id}
          className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500"
        >
          {label}
          {required ? <span className="ml-1 text-[#b91c1c]">*</span> : null}
        </label>
      ) : null}

      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listId : undefined}
        onClick={() => (isOpen ? closePicker() : openPicker())}
        onKeyDown={handleTriggerKeyDown}
        className={cn(
          'flex h-10 min-w-0 w-full items-center justify-between gap-2 rounded-sm border border-slate-200 bg-white px-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-[#1b3b87]',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        {selectedCourse ? (
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="text-sm font-bold text-slate-900">{selectedCourse.course_code}</span>
            <span className="truncate text-sm font-medium text-slate-500">
              {selectedCourse.course_title}
            </span>
          </span>
        ) : (
          <span className="min-w-0 truncate text-sm font-semibold text-slate-500">
            {placeholder}
          </span>
        )}
        <ChevronDown
          className={cn('size-4 shrink-0 text-slate-500 transition-transform', isOpen && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {isOpen ? (
        <div
          id={listId}
          role="listbox"
          aria-label={label ?? 'Courses'}
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-hidden rounded-sm border border-slate-200 bg-white"
        >
          <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2">
            <Search className="size-4 text-slate-400" aria-hidden="true" />
            <input
              ref={searchInputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setHighlightedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search by code or course title"
              className="min-w-0 flex-1 bg-transparent text-sm font-semibold text-slate-800 placeholder:text-slate-500 focus:outline-none"
              aria-autocomplete="list"
              aria-controls={listId}
            />
          </div>

          <div className="max-h-64 overflow-y-auto">
            {filteredCourses.length === 0 ? (
              <div className="px-3 py-4 text-center text-sm font-semibold text-slate-500">
                No courses found
              </div>
            ) : (
              filteredCourses.map((course, index) => {
                const isSelected = course.course_id === value;
                const isHighlighted = index === safeHighlightedIndex;
                return (
                  <button
                    key={course.course_id}
                    ref={(el) => {
                      itemRefs.current[index] = el;
                    }}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelect(course.course_id)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={cn(
                      'flex w-full items-center gap-2 px-3 py-2 text-left transition-colors focus:outline-none',
                      isHighlighted ? 'bg-[#1b3b87]/5' : 'bg-white hover:bg-slate-50/60',
                      isSelected && 'bg-[#1b3b87]/5',
                    )}
                  >
                    <span className="flex min-w-0 flex-1 items-baseline gap-2">
                      <span className="text-sm font-bold text-slate-900">{course.course_code}</span>
                      <span className="truncate text-sm font-medium text-slate-500">
                        {course.course_title}
                      </span>
                    </span>
                    {isSelected ? <Check className="size-4 shrink-0 text-[#1b3b87]" aria-hidden="true" /> : null}
                  </button>
                );
              })
            )}
          </div>
        </div>
      ) : null}

      {hint ? <p className="mt-2 text-xs font-medium text-slate-500">{hint}</p> : null}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd client && pnpm build`
Expected: compiles with no new TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add client/src/features/curriculumAlignment/components/CourseSelector.tsx
git commit -m "feat(curriculum-alignment): add CourseSelector combobox"
```

---

### Task 14: AlignmentResultsTable component

**Files:**
- Create: `client/src/features/curriculumAlignment/components/AlignmentResultsTable.tsx`

**Interfaces:**
- Consumes: `ObjectiveResult` (Task 10), `statusLabel`/`statusBadgeClasses` (Task 11).
- Produces: `<AlignmentResultsTable objectiveResults onEvidenceClick />` where `onEvidenceClick(pageNumber: number) => void` fires when a user clicks an evidence quote (wired to the reading pane's scroll-and-flash in Task 16). Consumed by `AlignmentCheckPage.tsx` (Task 15).

No isolated unit test — this is a presentational table with no business logic of its own (all status/color logic already tested in Task 11); it is exercised visually in Task 16's manual verification pass, matching this codebase's existing convention of not unit-testing presentational components like `Scorecard.tsx`.

- [ ] **Step 1: Write the component**

```typescript
// client/src/features/curriculumAlignment/components/AlignmentResultsTable.tsx
// Styled like evaluation/components/Scorecard.tsx's criterion table: same
// column rhythm, same nested evidence box under a row with a quote.
import { cn } from '@/shared/components/utils';
import { statusBadgeClasses, statusLabel } from '../utils/alignmentHelpers';
import type { ObjectiveResult } from '../types';

type AlignmentResultsTableProps = {
  objectiveResults: ObjectiveResult[];
  onEvidenceClick?: (pageNumber: number) => void;
};

export function AlignmentResultsTable({
  objectiveResults,
  onEvidenceClick,
}: AlignmentResultsTableProps) {
  if (objectiveResults.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-slate-200 bg-slate-50/30 px-4 py-6 text-center text-sm font-semibold text-slate-500">
        No mapped objectives for this course.
      </div>
    );
  }

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="text-left text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
          <th className="px-4 py-2">Objective</th>
          <th className="px-4 py-2">Expected</th>
          <th className="px-4 py-2">Observed</th>
          <th className="px-4 py-2">Status</th>
        </tr>
      </thead>
      <tbody>
        {objectiveResults.map((result) => (
          <tr key={result.code} className="border-t border-slate-100 align-top">
            <td className="px-4 py-3">
              <div className="text-sm font-semibold text-slate-800">{result.code}</div>
              <div className="text-xs text-slate-500">{result.description}</div>
              {result.evidence ? (
                <button
                  type="button"
                  onClick={() =>
                    result.evidence_page != null && onEvidenceClick?.(result.evidence_page)
                  }
                  className="mt-2 block w-full rounded-sm border border-slate-100 bg-slate-50 p-2.5 text-left text-xs font-medium leading-[1.6] text-slate-600 transition-colors hover:bg-slate-100"
                >
                  &ldquo;{result.evidence}&rdquo;
                </button>
              ) : null}
            </td>
            <td className="px-4 py-3 font-bold text-slate-800">{result.expected_level}</td>
            <td className="px-4 py-3 font-bold text-slate-800">{result.observed_level ?? '—'}</td>
            <td className="px-4 py-3">
              <span
                className={cn(
                  'inline-flex items-center rounded-sm border px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider',
                  statusBadgeClasses(result.status),
                )}
              >
                {statusLabel(result.status)}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd client && pnpm build`
Expected: compiles with no new TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add client/src/features/curriculumAlignment/components/AlignmentResultsTable.tsx
git commit -m "feat(curriculum-alignment): add results table component"
```

---

### Task 15: SlmReadingPane component

**Files:**
- Create: `client/src/features/curriculumAlignment/components/SlmReadingPane.tsx`

**Interfaces:**
- Consumes: `DocumentPage` (Task 10).
- Produces: `<SlmReadingPane pages />` rendering `id="page-${page_number}"` blocks, and imperatively exposes `scrollToPage(pageNumber: number)` via `useImperativeHandle` on a forwarded ref — mirrors `DocumentPane.tsx`'s exact scroll-and-flash mechanism (`scrollIntoView({behavior:'smooth', block:'center'})` + toggling `bg-[#f2c811]/15` for 1500ms), reimplemented locally (not imported) because `curriculumAlignment` must not import from the `evaluation` feature. Consumed by `AlignmentCheckPage.tsx` (Task 15).

No isolated unit test — this component's core behavior (`scrollIntoView`/`classList` timing) is JSDOM-unfriendly and it directly reimplements a mechanism already in production use in `DocumentPane.tsx`; it is exercised via manual browser verification in Task 16.

- [ ] **Step 1: Write the component**

```typescript
// client/src/features/curriculumAlignment/components/SlmReadingPane.tsx
// Read-only per-page SLM viewer for this feature's own reading pane.
// Deliberately NOT importing evaluation/components/DocumentPane.tsx --
// features must stay self-contained (CLAUDE.md module boundaries) -- so
// the click-to-scroll-and-flash mechanism is reimplemented here, matching
// DocumentPane's exact behavior (scrollIntoView + timed highlight class).
import { forwardRef, useImperativeHandle } from 'react';
import type { DocumentPage } from '../types';

export type SlmReadingPaneHandle = {
  scrollToPage: (pageNumber: number) => void;
};

type SlmReadingPaneProps = {
  pages: DocumentPage[];
};

export const SlmReadingPane = forwardRef<SlmReadingPaneHandle, SlmReadingPaneProps>(
  function SlmReadingPane({ pages }, ref) {
    useImperativeHandle(ref, () => ({
      scrollToPage: (pageNumber: number) => {
        setTimeout(() => {
          const el = window.document.getElementById(`page-${pageNumber}`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.classList.add('bg-[#f2c811]/15');
            setTimeout(() => {
              el.classList.remove('bg-[#f2c811]/15');
            }, 1500);
          }
        }, 150);
      },
    }));

    if (pages.length === 0) {
      return (
        <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-500">
          No document content available.
        </div>
      );
    }

    return (
      <div className="h-full overflow-y-auto bg-[#f8fafc] p-4">
        {pages.map((page) => (
          <div
            key={page.page_number}
            id={`page-${page.page_number}`}
            className="mb-3 rounded-sm border border-slate-200 bg-white p-4 transition-colors"
          >
            <div className="mb-2 text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
              Page {page.page_number}
            </div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
              {page.text}
            </div>
          </div>
        ))}
      </div>
    );
  },
);
```

- [ ] **Step 2: Type-check**

Run: `cd client && pnpm build`
Expected: compiles with no new TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add client/src/features/curriculumAlignment/components/SlmReadingPane.tsx
git commit -m "feat(curriculum-alignment): add SLM reading pane with click-to-scroll evidence linking"
```

---

### Task 16: AlignmentCheckPage, route, and nav entry

**Files:**
- Create: `client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx`
- Modify: `client/src/app/router.tsx`, `client/src/app/layout/Sidebar.tsx`

**Interfaces:**
- Consumes: `useCourses`, `useRunAlignmentCheck`, `useAlignmentCheck`, `useDocumentPages` (Task 12); `CourseSelector` (Task 13); `AlignmentResultsTable` (Task 14); `SlmReadingPane`, `SlmReadingPaneHandle` (Task 15); `documentsApi` (`@/shared/api/documents.api`, for the document picker — reused since it's already shared across 2+ features); `getErrorMessage` (`@/shared/api/http`).
- Produces: `AlignmentCheckPage` component, mounted at route `alignment`.

- [ ] **Step 1: Write the page**

```typescript
// client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx
import { useRef, useState } from 'react';
import { Loader2, AlertTriangle } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { documentsApi } from '@/shared/api/documents.api';
import { useQuery } from '@tanstack/react-query';
import { CourseSelector } from '../components/CourseSelector';
import { AlignmentResultsTable } from '../components/AlignmentResultsTable';
import { SlmReadingPane, type SlmReadingPaneHandle } from '../components/SlmReadingPane';
import { useCourses } from '../hooks/useCourses';
import { useRunAlignmentCheck } from '../hooks/useRunAlignmentCheck';
import { useDocumentPages } from '../hooks/useDocumentPages';

export function AlignmentCheckPage() {
  const [documentId, setDocumentId] = useState('');
  const [courseId, setCourseId] = useState('');
  const readingPaneRef = useRef<SlmReadingPaneHandle>(null);

  const { data: documentsData } = useQuery({
    queryKey: ['curriculum-map', 'documents-for-picker'],
    queryFn: () => documentsApi.listDocuments({ sourceType: 'slm', pageSize: 100 }),
  });
  const { data: coursesData, isLoading: coursesLoading } = useCourses();
  const runCheck = useRunAlignmentCheck();
  const { data: pagesData } = useDocumentPages(runCheck.data?.check_id ?? null);

  const documents = documentsData?.items ?? [];
  const courses = coursesData?.items ?? [];

  const handleRun = () => {
    if (!documentId || !courseId) return;
    runCheck.mutate({ documentId, courseId });
  };

  return (
    <div className="flex h-full flex-col gap-4 px-6 py-7">
      <div>
        <h1 className="text-lg font-bold text-slate-900">Curriculum Alignment Check</h1>
        <p className="text-sm text-slate-500">
          Check whether an SLM aligns with its course's curriculum map objectives.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-sm border border-slate-200 bg-white p-4">
        <div className="min-w-64 flex-1">
          <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
            Document
          </label>
          <select
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="h-10 w-full rounded-sm border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
          >
            <option value="">Select a document...</option>
            {documents.map((doc) => (
              <option key={doc.documentId} value={doc.documentId}>
                {doc.title}
              </option>
            ))}
          </select>
        </div>

        <div className="min-w-64 flex-1">
          <CourseSelector
            value={courseId}
            onChange={setCourseId}
            courses={courses}
            label="Course"
            disabled={coursesLoading}
          />
        </div>

        <button
          type="button"
          onClick={handleRun}
          disabled={!documentId || !courseId || runCheck.isPending}
          className="h-10 rounded-sm bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:cursor-not-allowed disabled:opacity-60"
        >
          Run Curriculum Alignment Check
        </button>
      </div>

      {runCheck.isPending ? (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="size-8 animate-spin text-[#1b3b87]" />
        </div>
      ) : null}

      {runCheck.isError ? (
        <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
          <AlertTriangle className="size-4 shrink-0" />
          {getErrorMessage(runCheck.error, 'Curriculum alignment check failed.')}
        </div>
      ) : null}

      {runCheck.data ? (
        <div className="grid flex-1 grid-cols-2 gap-4 overflow-hidden">
          <div className="overflow-hidden rounded-sm border border-slate-200">
            <SlmReadingPane ref={readingPaneRef} pages={pagesData?.pages ?? []} />
          </div>
          <div className="overflow-y-auto rounded-sm border border-slate-200 bg-white">
            <AlignmentResultsTable
              objectiveResults={runCheck.data.objective_results}
              onEvidenceClick={(pageNumber) => readingPaneRef.current?.scrollToPage(pageNumber)}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Add the route**

In `client/src/app/router.tsx`, add the import and route:

```typescript
import { AlignmentCheckPage } from '../features/curriculumAlignment/pages/AlignmentCheckPage';
```

```typescript
const alignmentRoute = createRoute({
  getParentRoute: () => shellRoute,
  path: 'alignment',
  component: AlignmentCheckPage,
});
```

Add `alignmentRoute` to `shellRoute.addChildren([...])`, alongside `matrixRoute`:

```typescript
const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  shellRoute.addChildren([
    dashboardRoute,
    uploadRoute,
    evaluationsRoute,
    documentEvaluationRoute,
    evaluationDetailRoute,
    matrixRoute,
    alignmentRoute,
    adminRoute.addChildren([
      // ...unchanged
    ]),
  ]),
]);
```

- [ ] **Step 3: Add the nav entry**

In `client/src/app/layout/Sidebar.tsx`, add `BookOpenCheck` (or reuse an existing unused icon — `BookOpen` is already imported for the admin "Logs" item, so import a distinct one) to the `lucide-react` import list, then add to `workspaceNavItems`:

```typescript
import {
  BookOpen,
  BookOpenCheck,
  ClipboardList,
  FilePlus2,
  FileUp,
  FolderOpen,
  LayoutDashboard,
  Library,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Shield,
  ScanSearch,
  Upload,
  Users,
  type LucideIcon,
} from 'lucide-react';
```

```typescript
const workspaceNavItems: readonly NavItem[] = [
  { to: '/dashboard', label: 'Documents', icon: FolderOpen, exact: true },
  { to: '/upload', label: 'Upload', icon: FilePlus2, exact: true },
  { to: '/evaluations', label: 'Evaluations', icon: ClipboardList, exact: true },
  { to: '/alignment', label: 'Curriculum Alignment', icon: BookOpenCheck, exact: true },
] as const;
```

- [ ] **Step 4: Type-check and lint**

Run: `cd client && pnpm build`
Expected: compiles with no new TypeScript errors

Run: `cd client && pnpm lint`
Expected: no new lint errors in the files touched this task

- [ ] **Step 5: Commit**

```bash
git add client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx client/src/app/router.tsx client/src/app/layout/Sidebar.tsx
git commit -m "feat(curriculum-alignment): add AlignmentCheckPage, route, and nav entry"
```

---

### Task 17: Seed the database and manually verify the full flow

**Files:** none (verification-only task)

**Interfaces:** none — this task exercises everything built in Tasks 1-16 end-to-end.

- [ ] **Step 1: Run the seed script against the dev database**

Run: `uv run --project server python -m server.scripts.seed_curriculum_map`
Expected: prints `Seeded curriculum map for program BSIT.`

- [ ] **Step 2: Start the backend**

Run: `uv run --project server uvicorn server.main:app --reload --host 0.0.0.0 --port 8000`
Expected: server starts; `GET /api/v1/curriculum-map/courses` (with a valid session cookie) returns the two seeded IT courses

- [ ] **Step 3: Start the frontend**

Run: `cd client && pnpm dev`
Expected: Vite dev server starts on `http://localhost:5173`

- [ ] **Step 4: Manually verify the feature in the browser**

Log in, navigate to "Curriculum Alignment" in the sidebar, select an already-uploaded SLM document and a seeded course, click "Run Curriculum Alignment Check," and confirm:
- The loading spinner appears while the check runs.
- Results render as a table with Objective / Expected / Observed / Status columns.
- Status badges use the graduated severity colors (green/light-blue/gold/red).
- Clicking an evidence quote scrolls the reading pane to the matching page and briefly highlights it.
- Selecting a course with no seeded objectives (if any) or an unmapped course surfaces a clear error, not a blank "all fine" result.

- [ ] **Step 5: Confirm the existing scoring pipeline is untouched**

Run: `uv run --project server pytest server/tests/agents/ -v`
Expected: PASS — no test in the existing `agents/` suite (SME/Coordinator/GAD/ITSO/supervisor) was modified or broken by this work

---

## Summary

17 tasks: 9 backend (migration → models → pure comparison logic → document text/evidence location → LLM check → service → schemas → router → seed script) and 8 frontend (types/API → status helper → hooks → CourseSelector → results table → reading pane → page/route/nav → manual verification). Each task is independently committable and testable, matching the "review and commit if it is okay" workflow.
