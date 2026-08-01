# Curriculum Alignment — Recent-Checks History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paginated history of past curriculum alignment checks to the `/alignment` page, letting a user reload or delete a past check, filling the currently-blank space below the document/course picker.

**Architecture:** Two new backend endpoints (`GET /curriculum-map/checks` list, `DELETE /curriculum-map/checks/{check_id}`) backed by two new service functions, both scoped by the existing document-ownership rule. On the frontend, a new `AlignmentHistoryList` component becomes the default content of `AlignmentCheckPage`, and a single `activeCheckId` state variable unifies "just ran a check" and "reloaded a past check" behind the same existing `useAlignmentCheck`/`useDocumentPages` hooks.

**Tech Stack:** FastAPI + SQLAlchemy + pytest (backend); React 18 + TanStack Query + Tailwind v4 + vitest (frontend). No new dependencies.

## Global Constraints

- Do not modify `server/modules/agents/scoring/curriculum_alignment.py`, `coordinator.py`, `sme.py`, `gad.py`, `itso.py`, or `supervisor.py` — this pipeline stays fully independent (design spec §Non-goals).
- Backend: ruff-enforced (E, F, I, UP), line length 88, Python 3.12.
- Frontend: TypeScript, ESLint, Prettier. `client/src/features/curriculumAlignment` must not import from other features (e.g. not from `dashboard`'s `DocumentPagination.tsx`) — build its own self-contained pagination controls, matching the same pattern `SlmReadingPane.tsx` already uses for its own click-to-scroll instead of importing `evaluation/components/DocumentPane.tsx`.
- No new frontend test dependency — this project has vitest only, no React Testing Library/jsdom rendering setup (verified: `client/package.json` has no `@testing-library/*` and no render-testing infra exists anywhere in `client/src`). Automated frontend tests in this plan are limited to pure-logic helpers (matching the existing `alignmentHelpers.test.ts` precedent); components are verified by build + lint + manual browser check, same as every existing component in this feature (`CourseSelector.tsx`, `AlignmentResultsTable.tsx`, `SlmReadingPane.tsx`, `AlignmentCheckPage.tsx` have no test files either).
- List payload stays lightweight: no `objective_results`/evidence in the list response — that's only fetched per-check via the existing `GET /checks/{check_id}`.
- Delete is a hard delete (no soft-delete/undo) — history rows are disposable, not an audit-of-record.
- Run backend commands from repo root: `uv run --project server pytest ...`. Run frontend commands from `client/`: `pnpm test`, `pnpm build`, `pnpm lint`.

---

## File Structure

**Backend — modified:**
- `server/modules/curriculum_map/service.py` — add `list_alignment_checks()`, `delete_alignment_check()`.
- `server/modules/curriculum_map/schemas.py` — add `AlignmentCheckListItemResponse`, `AlignmentCheckListResponse`.
- `server/modules/curriculum_map/router.py` — add `GET /checks` (list) and `DELETE /checks/{check_id}` endpoints.
- `server/tests/curriculum_map/test_service.py` — new tests for both service functions.
- `server/tests/curriculum_map/test_router.py` — new tests for both endpoints.

**Frontend — modified:**
- `client/src/features/curriculumAlignment/types.ts` — add `AlignmentCheckListItem`, `AlignmentCheckListResponse`.
- `client/src/features/curriculumAlignment/api/curriculumAlignment.api.ts` — add `listChecks()`, `deleteCheck()`.
- `client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx` — wire `activeCheckId` state, history list as default view, "Back to history" action.

**Frontend — new:**
- `client/src/features/curriculumAlignment/hooks/useAlignmentCheckHistory.ts`
- `client/src/features/curriculumAlignment/hooks/useDeleteAlignmentCheck.ts`
- `client/src/features/curriculumAlignment/utils/historyHelpers.ts` — `formatSummaryChips()`.
- `client/src/features/curriculumAlignment/utils/__tests__/historyHelpers.test.ts`
- `client/src/features/curriculumAlignment/components/AlignmentHistoryList.tsx`

---

### Task 1: Backend service functions — list and delete

**Files:**
- Modify: `server/modules/curriculum_map/service.py`
- Test: `server/tests/curriculum_map/test_service.py`

**Interfaces:**
- Consumes: `CurriculumAlignmentCheck`, `Course` (already imported in `service.py`), `Document` (imported locally inside the function, matching the existing `_require_owned_document` pattern at `service.py:76-92`), `_require_owned_document()` (existing, `service.py:76`), `AlignmentCheckNotFoundError`/`DocumentAccessDeniedError` (existing, `exceptions.py`).
- Produces: `list_alignment_checks(*, current_user_id: uuid.UUID, page: int, page_size: int, db: Any) -> tuple[list[dict[str, Any]], int]` — each dict has keys `check_id`, `document_id`, `document_title`, `course_id`, `course_title`, `run_at`, `success`, `error_message`, `summary`. `delete_alignment_check(check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any) -> None`. Both consumed by `router.py` in Task 2.

- [ ] **Step 1: Write the failing tests**

Add to `server/tests/curriculum_map/test_service.py`. First, update the existing import block at the top of the file to also import `CurriculumAlignmentCheck`:

```python
from server.modules.curriculum_map.models import (
    Course,
    CurriculumAlignmentCheck,
    CurriculumMapCell,
    CurriculumObjective,
)
```

Then append these tests at the end of the file:

```python
def test_list_checks_returns_only_current_users_checks_newest_first(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    other_owner = uuid.uuid4()

    mine_doc = _make_document(db_session, uploaded_by=owner)
    other_doc = _make_document(db_session, uploaded_by=other_owner)

    older = CurriculumAlignmentCheck(
        document_id=mine_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(older)
    db_session.commit()

    newer = CurriculumAlignmentCheck(
        document_id=mine_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(newer)
    db_session.commit()

    not_mine = CurriculumAlignmentCheck(
        document_id=other_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(not_mine)
    db_session.commit()

    items, total = service.list_alignment_checks(
        current_user_id=owner, page=1, page_size=20, db=db_session
    )
    assert total == 2
    assert [i["check_id"] for i in items] == [newer.check_id, older.check_id]
    assert items[0]["document_title"] == "Sample SLM"
    assert items[0]["course_title"] == "Data Structures"


def test_list_checks_paginates(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

    for _ in range(3):
        db_session.add(
            CurriculumAlignmentCheck(
                document_id=document.document_id,
                course_id=course.course_id,
                objective_results=[],
                summary={"total_mapped_objectives": 0},
                success=True,
            )
        )
        db_session.commit()

    page_1, total = service.list_alignment_checks(
        current_user_id=owner, page=1, page_size=2, db=db_session
    )
    page_2, _ = service.list_alignment_checks(
        current_user_id=owner, page=2, page_size=2, db=db_session
    )
    assert total == 3
    assert len(page_1) == 2
    assert len(page_2) == 1


def test_list_checks_returns_empty_for_user_with_none(db_session) -> None:
    items, total = service.list_alignment_checks(
        current_user_id=uuid.uuid4(), page=1, page_size=20, db=db_session
    )
    assert items == []
    assert total == 0


def test_delete_check_removes_row(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()
    check_id = check.check_id

    service.delete_alignment_check(check_id, owner, db_session)

    assert db_session.get(CurriculumAlignmentCheck, check_id) is None


def test_delete_check_raises_for_nonexistent_check(db_session) -> None:
    with pytest.raises(AlignmentCheckNotFoundError):
        service.delete_alignment_check(uuid.uuid4(), uuid.uuid4(), db_session)


def test_delete_check_raises_for_non_owner(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    other_user = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    with pytest.raises(DocumentAccessDeniedError):
        service.delete_alignment_check(check.check_id, other_user, db_session)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/curriculum_map/test_service.py -v -k "list_checks or delete_check"`
Expected: FAIL with `AttributeError: module 'server.modules.curriculum_map.service' has no attribute 'list_alignment_checks'`

- [ ] **Step 3: Implement the two service functions**

Append to `server/modules/curriculum_map/service.py`, before the `__all__` declaration:

```python
def list_alignment_checks(
    *,
    current_user_id: uuid.UUID,
    page: int,
    page_size: int,
    db: Any,
) -> tuple[list[dict[str, Any]], int]:
    """Return (items, total) of this user's past checks, newest first.

    Joins CurriculumAlignmentCheck -> Document (ownership filter + title)
    -> Course (title). Deliberately excludes objective_results/evidence --
    those are only fetched per-check via get_alignment_check.
    """
    from server.modules.documents.models import Document

    query = (
        db.query(CurriculumAlignmentCheck, Document.title, Course.course_title)
        .join(Document, CurriculumAlignmentCheck.document_id == Document.document_id)
        .join(Course, CurriculumAlignmentCheck.course_id == Course.course_id)
        .filter(Document.uploaded_by == current_user_id)
        .order_by(CurriculumAlignmentCheck.run_at.desc())
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "check_id": check.check_id,
            "document_id": check.document_id,
            "document_title": document_title,
            "course_id": check.course_id,
            "course_title": course_title,
            "run_at": check.run_at,
            "success": check.success,
            "error_message": check.error_message,
            "summary": check.summary,
        }
        for check, document_title, course_title in rows
    ]
    return items, total


def delete_alignment_check(
    check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> None:
    """Delete one check. Ownership-checked the same way get_alignment_check
    is: the check must exist and its document must belong to the caller.
    """
    check = db.get(CurriculumAlignmentCheck, check_id)
    if check is None:
        raise AlignmentCheckNotFoundError(f"Alignment check {check_id} not found")
    _require_owned_document(check.document_id, current_user_id, db)
    db.delete(check)
    db.commit()
```

Update the `__all__` list at the bottom of `server/modules/curriculum_map/service.py` to add the two new names:

```python
__all__ = [
    "list_courses",
    "list_alignment_checks",
    "run_curriculum_alignment_check",
    "get_alignment_check",
    "get_document_pages_for_check",
    "delete_alignment_check",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/curriculum_map/test_service.py -v`
Expected: PASS (all tests in the file, including the new ones)

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/modules/curriculum_map/service.py server/tests/curriculum_map/test_service.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add server/modules/curriculum_map/service.py server/tests/curriculum_map/test_service.py
git commit -m "feat(curriculum-map): add list/delete service functions for check history"
```

---

### Task 2: Backend schemas and endpoints

**Files:**
- Modify: `server/modules/curriculum_map/schemas.py`
- Modify: `server/modules/curriculum_map/router.py`
- Test: `server/tests/curriculum_map/test_router.py`

**Interfaces:**
- Consumes: `list_alignment_checks()`, `delete_alignment_check()` (Task 1), `AlignmentCheckSummary` (existing, `schemas.py:34`), `AlignmentCheckNotFoundError`/`DocumentAccessDeniedError` (existing).
- Produces: `AlignmentCheckListItemResponse`, `AlignmentCheckListResponse` (consumed by the frontend types in Task 3). Endpoints `GET /api/v1/curriculum-map/checks?page=&page_size=` and `DELETE /api/v1/curriculum-map/checks/{check_id}`.

- [ ] **Step 1: Write the failing router tests**

Update the import block at the top of `server/tests/curriculum_map/test_router.py` to also import `CurriculumAlignmentCheck`:

```python
from server.modules.curriculum_map.models import Course, CurriculumAlignmentCheck
```

Append these tests at the end of the file:

```python
def test_list_checks_requires_auth(client) -> None:
    response = client.get("/api/v1/curriculum-map/checks")
    assert response.status_code == 401


def test_list_checks_returns_only_current_users_checks(client, db_session) -> None:
    user = _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    document = Document(
        title="Sample SLM", source_type="slm", file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
    )
    db_session.add_all([course, document])
    db_session.commit()

    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    response = client.get("/api/v1/curriculum-map/checks")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["items"][0]["check_id"] == str(check.check_id)
    assert body["items"][0]["document_title"] == "Sample SLM"
    assert body["items"][0]["course_title"] == "Data Structures"


def test_list_checks_returns_empty_items_for_new_user(client, db_session) -> None:
    _login(client, db_session)
    response = client.get("/api/v1/curriculum-map/checks")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_delete_check_returns_404_for_unknown_id(client, db_session) -> None:
    _login(client, db_session)
    response = client.delete(f"/api/v1/curriculum-map/checks/{uuid.uuid4()}")
    assert response.status_code == 404


def test_delete_check_returns_404_for_non_owner_check(client, db_session) -> None:
    _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    other_owner_document = Document(
        title="Not mine", source_type="slm", file_path="/tmp/x.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add_all([course, other_owner_document])
    db_session.commit()
    check = CurriculumAlignmentCheck(
        document_id=other_owner_document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    response = client.delete(f"/api/v1/curriculum-map/checks/{check.check_id}")
    assert response.status_code == 404


def test_delete_check_succeeds_for_owner(client, db_session) -> None:
    user = _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    document = Document(
        title="Sample SLM", source_type="slm", file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
    )
    db_session.add_all([course, document])
    db_session.commit()
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    response = client.delete(f"/api/v1/curriculum-map/checks/{check.check_id}")
    assert response.status_code == 204
    assert db_session.get(CurriculumAlignmentCheck, check.check_id) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/curriculum_map/test_router.py -v -k "list_checks or delete_check"`
Expected: FAIL with 404 (route doesn't exist yet) for the list tests, and 405/404 for the delete tests.

- [ ] **Step 3: Add the schemas**

In `server/modules/curriculum_map/schemas.py`, insert after `AlignmentCheckResponse` (and before `DocumentPageResponse`):

```python
class AlignmentCheckListItemResponse(BaseModel):
    check_id: UUID
    document_id: UUID
    document_title: str
    course_id: UUID
    course_title: str
    run_at: datetime
    success: bool
    error_message: str | None = None
    summary: AlignmentCheckSummary


class AlignmentCheckListResponse(BaseModel):
    items: list[AlignmentCheckListItemResponse]
    total: int
    page: int
    page_size: int
```

Update `__all__` at the bottom of `schemas.py` to add the two new names:

```python
__all__ = [
    "CourseResponse",
    "CourseListResponse",
    "ObjectiveResultResponse",
    "AlignmentCheckSummary",
    "RunAlignmentCheckRequest",
    "AlignmentCheckResponse",
    "AlignmentCheckListItemResponse",
    "AlignmentCheckListResponse",
    "DocumentPageResponse",
    "DocumentPagesResponse",
]
```

- [ ] **Step 4: Add the endpoints**

In `server/modules/curriculum_map/router.py`, update the `fastapi` import to include `Query`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
```

Update the `.schemas` import block to add the two new response types:

```python
from .schemas import (
    AlignmentCheckListItemResponse,
    AlignmentCheckListResponse,
    AlignmentCheckResponse,
    CourseListResponse,
    CourseResponse,
    DocumentPageResponse,
    DocumentPagesResponse,
    RunAlignmentCheckRequest,
)
```

Update the `.service` import block to add the two new functions:

```python
from .service import (
    delete_alignment_check,
    get_alignment_check,
    get_document_pages_for_check,
    list_alignment_checks,
    list_courses,
    run_curriculum_alignment_check,
)
```

Insert a new `list_checks_endpoint` right after `list_courses_endpoint` (before `run_check_endpoint`):

```python
@router.get("/checks", response_model=AlignmentCheckListResponse)
def list_checks_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> AlignmentCheckListResponse:
    items, total = list_alignment_checks(
        current_user_id=_current_user.id, page=page, page_size=page_size, db=db
    )
    return AlignmentCheckListResponse(
        items=[AlignmentCheckListItemResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
```

Insert a new `delete_check_endpoint` right after `get_check_endpoint` (before `get_document_pages_endpoint`):

```python
@router.delete("/checks/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_check_endpoint(
    check_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> None:
    try:
        delete_alignment_check(check_id, _current_user.id, db)
    except (AlignmentCheckNotFoundError, DocumentAccessDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/curriculum_map/test_router.py -v`
Expected: PASS (all tests in the file, including the new ones)

- [ ] **Step 6: Run the full curriculum_map suite and lint**

Run: `uv run --project server pytest server/tests/curriculum_map/ -v`
Expected: PASS (all tests)

Run: `uv run --project server ruff check server/modules/curriculum_map server/tests/curriculum_map`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add server/modules/curriculum_map/schemas.py server/modules/curriculum_map/router.py server/tests/curriculum_map/test_router.py
git commit -m "feat(curriculum-map): add list/delete endpoints for check history"
```

---

### Task 3: Frontend types and API layer

**Files:**
- Modify: `client/src/features/curriculumAlignment/types.ts`
- Modify: `client/src/features/curriculumAlignment/api/curriculumAlignment.api.ts`

**Interfaces:**
- Consumes: `AlignmentCheckSummary` (existing, `types.ts:25`), `requestJson` (existing, `@/shared/api/http`).
- Produces: `AlignmentCheckListItem`, `AlignmentCheckListResponse` (consumed by Task 4's hooks and Task 6's component). `curriculumAlignmentApi.listChecks(page, pageSize)`, `curriculumAlignmentApi.deleteCheck(checkId)` (consumed by Task 4's hooks).

No automated test for this task — mirrors the existing convention in this feature, where `types.ts` and `curriculumAlignment.api.ts` are thin pass-through layers with no dedicated test file (verified instead by `tsc` via the build step and by the router/service tests in Tasks 1-2 exercising the real HTTP contract these types describe).

- [ ] **Step 1: Add the list types**

Append to the end of `client/src/features/curriculumAlignment/types.ts`:

```ts
export interface AlignmentCheckListItem {
  check_id: string;
  document_id: string;
  document_title: string;
  course_id: string;
  course_title: string;
  run_at: string;
  success: boolean;
  error_message: string | null;
  summary: AlignmentCheckSummary;
}

export interface AlignmentCheckListResponse {
  items: AlignmentCheckListItem[];
  total: number;
  page: number;
  page_size: number;
}
```

- [ ] **Step 2: Add the API methods**

In `client/src/features/curriculumAlignment/api/curriculumAlignment.api.ts`, update the type-only import to include the new response type:

```ts
import type {
  AlignmentCheck,
  AlignmentCheckListResponse,
  CourseListResponse,
  DocumentPagesResponse,
} from '../types';
```

Add two methods to the `curriculumAlignmentApi` object, after `getDocumentPages`:

```ts
  listChecks: async (page: number, pageSize: number): Promise<AlignmentCheckListResponse> => {
    return requestJson<AlignmentCheckListResponse>(
      `/curriculum-map/checks?page=${page}&page_size=${pageSize}`,
    );
  },

  deleteCheck: async (checkId: string): Promise<void> => {
    await requestJson<void>(`/curriculum-map/checks/${checkId}`, { method: 'DELETE' });
  },
```

- [ ] **Step 3: Type-check**

Run (from `client/`): `pnpm build`
Expected: builds successfully with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add client/src/features/curriculumAlignment/types.ts client/src/features/curriculumAlignment/api/curriculumAlignment.api.ts
git commit -m "feat(curriculum-map): add types and API methods for check history"
```

---

### Task 4: Frontend hooks — history query and delete mutation

**Files:**
- Create: `client/src/features/curriculumAlignment/hooks/useAlignmentCheckHistory.ts`
- Create: `client/src/features/curriculumAlignment/hooks/useDeleteAlignmentCheck.ts`

**Interfaces:**
- Consumes: `curriculumAlignmentApi.listChecks`, `curriculumAlignmentApi.deleteCheck` (Task 3).
- Produces: `useAlignmentCheckHistory(page: number, pageSize: number)` and `useDeleteAlignmentCheck()`, both consumed by Task 6's `AlignmentHistoryList` component. The query key `['curriculum-map', 'checks', page, pageSize]` is also invalidated by name-prefix `['curriculum-map', 'checks']` from Task 7's run-success handler — keep this exact key shape.

No automated test for this task — mirrors the existing convention (`useCourses.ts`, `useRunAlignmentCheck.ts`, `useDocumentPages.ts` have no test files either); verified via the build step and manual browser check in Task 7.

- [ ] **Step 1: Write the history query hook**

```ts
// client/src/features/curriculumAlignment/hooks/useAlignmentCheckHistory.ts
import { useQuery } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useAlignmentCheckHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: ['curriculum-map', 'checks', page, pageSize],
    queryFn: () => curriculumAlignmentApi.listChecks(page, pageSize),
  });
}
```

- [ ] **Step 2: Write the delete mutation hook**

```ts
// client/src/features/curriculumAlignment/hooks/useDeleteAlignmentCheck.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useDeleteAlignmentCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (checkId: string) => curriculumAlignmentApi.deleteCheck(checkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['curriculum-map', 'checks'] });
    },
  });
}
```

- [ ] **Step 3: Type-check**

Run (from `client/`): `pnpm build`
Expected: builds successfully with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add client/src/features/curriculumAlignment/hooks/useAlignmentCheckHistory.ts client/src/features/curriculumAlignment/hooks/useDeleteAlignmentCheck.ts
git commit -m "feat(curriculum-map): add history and delete hooks"
```

---

### Task 5: Frontend pure helper — summary chip formatting

**Files:**
- Create: `client/src/features/curriculumAlignment/utils/historyHelpers.ts`
- Test: `client/src/features/curriculumAlignment/utils/__tests__/historyHelpers.test.ts`

**Interfaces:**
- Consumes: `AlignmentCheckSummary` (existing, `types.ts:25`).
- Produces: `formatSummaryChips(summary: AlignmentCheckSummary): string`, consumed by Task 6's `AlignmentHistoryList` component.

- [ ] **Step 1: Write the failing test**

```ts
// client/src/features/curriculumAlignment/utils/__tests__/historyHelpers.test.ts
import { describe, expect, it } from 'vitest';
import { formatSummaryChips } from '../historyHelpers';

describe('formatSummaryChips', () => {
  it('formats all four counts in order, including zeros', () => {
    const summary = {
      total_mapped_objectives: 6,
      match: 2,
      under_developed: 1,
      over_developed: 0,
      not_addressed: 3,
    };
    expect(formatSummaryChips(summary)).toBe('2 match · 1 under · 0 over · 3 not addressed');
  });

  it('handles an all-zero summary', () => {
    const summary = {
      total_mapped_objectives: 0,
      match: 0,
      under_developed: 0,
      over_developed: 0,
      not_addressed: 0,
    };
    expect(formatSummaryChips(summary)).toBe('0 match · 0 under · 0 over · 0 not addressed');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `client/`): `pnpm test -- historyHelpers`
Expected: FAIL — `historyHelpers.ts` doesn't exist yet.

- [ ] **Step 3: Implement the helper**

```ts
// client/src/features/curriculumAlignment/utils/historyHelpers.ts
// Single source of truth for turning a check's summary counts into the
// compact chip line shown per history row, mirroring the pattern
// alignmentHelpers.ts uses for status -> label/color.
import type { AlignmentCheckSummary } from '../types';

const CHIP_ORDER: Array<{ key: keyof AlignmentCheckSummary; label: string }> = [
  { key: 'match', label: 'match' },
  { key: 'under_developed', label: 'under' },
  { key: 'over_developed', label: 'over' },
  { key: 'not_addressed', label: 'not addressed' },
];

export function formatSummaryChips(summary: AlignmentCheckSummary): string {
  return CHIP_ORDER.map(({ key, label }) => `${summary[key]} ${label}`).join(' · ');
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `client/`): `pnpm test -- historyHelpers`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add client/src/features/curriculumAlignment/utils/historyHelpers.ts client/src/features/curriculumAlignment/utils/__tests__/historyHelpers.test.ts
git commit -m "feat(curriculum-map): add summary-chip formatting helper"
```

---

### Task 6: Frontend `AlignmentHistoryList` component

**Files:**
- Create: `client/src/features/curriculumAlignment/components/AlignmentHistoryList.tsx`

**Interfaces:**
- Consumes: `useAlignmentCheckHistory` (Task 4), `useDeleteAlignmentCheck` (Task 4), `formatSummaryChips` (Task 5), `AlignmentCheckListItem` (Task 3), `getErrorMessage` (existing, `@/shared/api/http`).
- Produces: `AlignmentHistoryList({ onSelect: (item: AlignmentCheckListItem) => void })`, consumed by Task 7's `AlignmentCheckPage.tsx`.

No automated test for this task (no rendering test infra in this project — see Global Constraints). Verified in Task 7's manual browser check, since this component only renders meaningfully once wired into the page.

- [ ] **Step 1: Implement the component**

```tsx
// client/src/features/curriculumAlignment/components/AlignmentHistoryList.tsx
// Self-contained pagination -- deliberately NOT importing
// dashboard/components/DocumentPagination.tsx, since features must stay
// self-contained (CLAUDE.md module boundaries). Same reasoning
// SlmReadingPane.tsx already documents for its own click-to-scroll reimpl.
import { useState } from 'react';
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { useAlignmentCheckHistory } from '../hooks/useAlignmentCheckHistory';
import { useDeleteAlignmentCheck } from '../hooks/useDeleteAlignmentCheck';
import { formatSummaryChips } from '../utils/historyHelpers';
import type { AlignmentCheckListItem } from '../types';

const PAGE_SIZE = 20;

type AlignmentHistoryListProps = {
  onSelect: (item: AlignmentCheckListItem) => void;
};

export function AlignmentHistoryList({ onSelect }: AlignmentHistoryListProps) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error } = useAlignmentCheckHistory(page, PAGE_SIZE);
  const deleteCheck = useDeleteAlignmentCheck();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);

  const handleDelete = (item: AlignmentCheckListItem, event: React.MouseEvent) => {
    event.stopPropagation();
    const confirmed = window.confirm(
      `Delete this check (${item.document_title} / ${item.course_title})?`,
    );
    if (!confirmed) return;
    deleteCheck.mutate(item.check_id);
  };

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-8 animate-spin text-[#1b3b87]" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
        <AlertTriangle className="size-4 shrink-0" />
        {getErrorMessage(error, 'Could not load check history.')}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-sm border border-dashed border-slate-200 bg-slate-50/30 p-8 text-center text-sm font-semibold text-slate-500">
        No checks yet. Pick a document and course above, then run a check to see it here.
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-sm border border-slate-200 bg-white">
      <div className="flex-1 divide-y divide-slate-100 overflow-y-auto">
        {items.map((item) => (
          <div
            key={item.check_id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(item)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect(item);
              }
            }}
            className="flex cursor-pointer items-start justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#1b3b87]"
          >
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-slate-800">
                {item.document_title}
                <span className="mx-1.5 text-slate-300">/</span>
                <span className="text-slate-600">{item.course_title}</span>
              </div>
              <div className="mt-1 text-xs text-slate-500">
                {new Date(item.run_at).toLocaleString()}
              </div>
              <div className="mt-1 text-xs font-medium text-slate-600">
                {item.success
                  ? formatSummaryChips(item.summary)
                  : `Failed: ${item.error_message ?? 'unknown error'}`}
              </div>
            </div>
            <button
              type="button"
              onClick={(e) => handleDelete(item, e)}
              aria-label="Delete check"
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-sm text-slate-400 transition-colors hover:bg-[#b91c1c]/10 hover:text-[#b91c1c] focus:outline-none focus:ring-2 focus:ring-[#b91c1c]"
            >
              <Trash2 className="size-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/30 px-4 py-3">
        <button
          type="button"
          disabled={page === 1}
          onClick={() => setPage((p) => Math.max(p - 1, 1))}
          className="inline-flex h-8 items-center justify-center rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>
        <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Page {page} of {totalPages}
        </span>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
          className="inline-flex h-8 items-center justify-center rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check and lint**

Run (from `client/`): `pnpm build`
Expected: builds successfully with no TypeScript errors.

Run (from `client/`): `pnpm lint`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add client/src/features/curriculumAlignment/components/AlignmentHistoryList.tsx
git commit -m "feat(curriculum-map): add AlignmentHistoryList component"
```

---

### Task 7: Wire history into `AlignmentCheckPage`

**Files:**
- Modify: `client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx`

**Interfaces:**
- Consumes: `AlignmentHistoryList` (Task 6), `useAlignmentCheck` (existing, `hooks/useAlignmentCheck.ts` — previously unused), `useDocumentPages` (existing), `useRunAlignmentCheck` (existing), `AlignmentCheckListItem` (Task 3).
- Produces: the finished page — no further tasks depend on this one.

No automated test for this task (page composition, no rendering infra). Verified by build + lint + a manual browser walkthrough below.

- [ ] **Step 1: Replace the page component**

Replace the full contents of `client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx` with:

```tsx
// client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx
import { useRef, useState } from 'react';
import { Loader2, AlertTriangle } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { documentsApi } from '@/shared/api/documents.api';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CourseSelector } from '../components/CourseSelector';
import { AlignmentResultsTable } from '../components/AlignmentResultsTable';
import { AlignmentHistoryList } from '../components/AlignmentHistoryList';
import { SlmReadingPane, type SlmReadingPaneHandle } from '../components/SlmReadingPane';
import { useCourses } from '../hooks/useCourses';
import { useRunAlignmentCheck } from '../hooks/useRunAlignmentCheck';
import { useAlignmentCheck } from '../hooks/useAlignmentCheck';
import { useDocumentPages } from '../hooks/useDocumentPages';
import type { AlignmentCheckListItem } from '../types';

export function AlignmentCheckPage() {
  const [documentId, setDocumentId] = useState('');
  const [courseId, setCourseId] = useState('');
  const [activeCheckId, setActiveCheckId] = useState<string | null>(null);
  const readingPaneRef = useRef<SlmReadingPaneHandle>(null);
  const queryClient = useQueryClient();

  const { data: documentsData } = useQuery({
    queryKey: ['curriculum-map', 'documents-for-picker'],
    queryFn: () => documentsApi.listDocuments({ sourceType: 'slm', pageSize: 100 }),
  });
  const { data: coursesData, isLoading: coursesLoading } = useCourses();
  const runCheck = useRunAlignmentCheck();
  const activeCheck = useAlignmentCheck(activeCheckId);
  const { data: pagesData } = useDocumentPages(activeCheckId);

  const documents = documentsData?.items ?? [];
  const courses = coursesData?.items ?? [];

  const handleRun = () => {
    if (!documentId || !courseId) return;
    runCheck.mutate(
      { documentId, courseId },
      {
        onSuccess: (data) => {
          setActiveCheckId(data.check_id);
          queryClient.invalidateQueries({ queryKey: ['curriculum-map', 'checks'] });
        },
      },
    );
  };

  const handleSelectHistoryItem = (item: AlignmentCheckListItem) => {
    setDocumentId(item.document_id);
    setCourseId(item.course_id);
    setActiveCheckId(item.check_id);
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

      {!runCheck.isPending && !runCheck.isError && activeCheckId === null ? (
        <AlignmentHistoryList onSelect={handleSelectHistoryItem} />
      ) : null}

      {!runCheck.isPending && !runCheck.isError && activeCheckId !== null ? (
        <div className="flex flex-1 flex-col gap-3 overflow-hidden">
          <button
            type="button"
            onClick={() => setActiveCheckId(null)}
            className="self-start text-xs font-bold uppercase tracking-wider text-[#1b3b87] hover:underline"
          >
            ← Back to history
          </button>

          {activeCheck.isLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <Loader2 className="size-8 animate-spin text-[#1b3b87]" />
            </div>
          ) : null}

          {activeCheck.data && !activeCheck.data.success ? (
            <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
              <AlertTriangle className="size-4 shrink-0" />
              {activeCheck.data.error_message ?? 'Curriculum alignment check failed.'}
            </div>
          ) : null}

          {activeCheck.data && activeCheck.data.success ? (
            <div className="grid flex-1 grid-cols-2 gap-4 overflow-hidden">
              <div className="overflow-hidden rounded-sm border border-slate-200">
                <SlmReadingPane ref={readingPaneRef} pages={pagesData?.pages ?? []} />
              </div>
              <div className="overflow-y-auto rounded-sm border border-slate-200 bg-white">
                <AlignmentResultsTable
                  objectiveResults={activeCheck.data.objective_results}
                  onEvidenceClick={(pageNumber) => readingPaneRef.current?.scrollToPage(pageNumber)}
                />
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Type-check, lint, build**

Run (from `client/`): `pnpm build`
Expected: builds successfully with no TypeScript errors.

Run (from `client/`): `pnpm lint`
Expected: no errors.

- [ ] **Step 3: Manual browser verification**

Run (from `client/`): `pnpm dev`, and in a separate terminal (from repo root):
`uv run --project server uvicorn server.main:app --reload --host 0.0.0.0 --port 8000`

In the browser:
1. Navigate to `/alignment`. Confirm the history list (or its empty state) shows below the picker instead of blank space.
2. Pick a document + course, click "Run Curriculum Alignment Check." Confirm results show, and confirm the run now appears at the top of history when you click "← Back to history."
3. Click a past history row. Confirm the pickers update to match, and the same results view loads without re-running the LLM check.
4. Click the delete icon on a row, confirm the browser confirm dialog, confirm, and confirm the row disappears from the list.
5. Confirm the existing SME/Coordinator/GAD/ITSO evaluation flow is untouched (spot-check `/evaluations`).

- [ ] **Step 4: Run the full test suites one more time**

Run: `uv run --project server pytest server/tests/curriculum_map/ -v`
Expected: PASS (all tests)

Run (from `client/`): `pnpm test`
Expected: PASS (all tests, including the new `historyHelpers.test.ts`)

- [ ] **Step 5: Commit**

```bash
git add client/src/features/curriculumAlignment/pages/AlignmentCheckPage.tsx
git commit -m "feat(curriculum-map): wire recent-checks history into the alignment page"
```
