# Curriculum Alignment — Recent-Checks History Design

Date: 2026-08-01
Branch: `feat/curriculum-alignment-pipeline`
Builds on: `docs/superpowers/specs/2026-07-30-curriculum-alignment-pipeline-design.md`

## Problem

The Curriculum Alignment Check page (`/alignment`) currently shows a large
blank area below the document/course picker until a check is run, and any
result is lost on page refresh — it only lives in the `runCheck` mutation's
in-memory state. Every run is already persisted to
`curriculum_alignment_checks`, and a `useAlignmentCheck(checkId)` hook
already exists to fetch one by ID, but nothing lists past checks or wires
that hook up.

## Goals

- Show the user's past curriculum alignment checks (any document/course),
  newest first, fully paginated.
- Clicking a past check loads its results in place, using the same results
  view as a fresh run.
- Let the user delete old check records.
- Fill the blank space below the picker with this list by default.

## Non-goals

- No changes to how a check is run or scored (Task 1-17 pipeline is
  untouched).
- No custom confirm-dialog primitive — reuse `window.confirm` for delete
  confirmation, since the app doesn't have one yet and building one is out
  of scope here.
- No cross-user visibility — history is still fully scoped to
  `document.uploaded_by`, same ownership rule as the rest of this module.

## Backend

### New service functions (`server/modules/curriculum_map/service.py`)

```python
def list_alignment_checks(
    *, current_user_id: uuid.UUID, page: int, page_size: int, db: Any
) -> tuple[list[CurriculumAlignmentCheck], int, dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    """Return (checks, total_count, document_titles_by_id, course_titles_by_id)
    for this user only, newest first.

    Joins CurriculumAlignmentCheck -> Document (filter uploaded_by) ->
    Course, ordered by run_at desc, offset/limit paginated.
    """

def delete_alignment_check(
    check_id: uuid.UUID, current_user_id: uuid.UUID, db: Any
) -> None:
    """Delete one check. Raises AlignmentCheckNotFoundError /
    DocumentAccessDeniedError (reusing existing exceptions) if it doesn't
    exist or isn't owned by current_user_id.
    """
```

### New schemas (`server/modules/curriculum_map/schemas.py`)

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

Deliberately lighter than `AlignmentCheckResponse` — no
`objective_results`/evidence in the list payload; that's only fetched when
a specific check is opened via the existing `GET /checks/{check_id}`.

### New endpoints (`server/modules/curriculum_map/router.py`)

- `GET /curriculum-map/checks?page=1&page_size=20` →
  `AlignmentCheckListResponse`. Requires auth. Empty list (not an error) if
  the user has no checks yet.
- `DELETE /curriculum-map/checks/{check_id}` → 204 No Content. 404 via the
  existing `AlignmentCheckNotFoundError`/`DocumentAccessDeniedError` →
  `HTTPException(404)` mapping already used elsewhere in this router.

No changes to `GET /checks/{check_id}` or
`GET /checks/{check_id}/document-pages` — reused as-is for reload.

## Frontend

### State model: single source of truth

`AlignmentCheckPage` currently renders results straight from the
`runCheck` mutation's response. Adding history introduces a second way to
arrive at "show these results" (clicking a past check), so both paths are
unified behind one piece of state:

```ts
const [activeCheckId, setActiveCheckId] = useState<string | null>(null);
```

- Running a new check: on `runCheck` success, call
  `setActiveCheckId(response.check_id)` and invalidate the history list
  query so the new run appears at the top immediately.
- Clicking a history row: call `setActiveCheckId(row.check_id)` and update
  the document/course pickers to match that row's `document_id`/
  `course_id` (so re-running is one click away).
- The results panel always renders from `useAlignmentCheck(activeCheckId)`
  (existing hook) + `useDocumentPages(activeCheckId)` (existing hook) —
  one code path for fresh and reloaded results, at the cost of one
  redundant `GET` right after a fresh run's `POST` (cheap DB read, no LLM
  call, so this tradeoff is fine).
- `activeCheckId === null` → show the history list instead of results.
  Results view gets a "← Back to history" action that just clears
  `activeCheckId` (the history query stays cached, no refetch needed).

### New API layer additions (`api/curriculumAlignment.api.ts`)

```ts
listChecks(page: number, pageSize: number): Promise<AlignmentCheckListResponse>
deleteCheck(checkId: string): Promise<void>
```

### New hooks

- `useAlignmentCheckHistory(page, pageSize)` — `useQuery`, key
  `['curriculum-map', 'checks', page, pageSize]`.
- `useDeleteAlignmentCheck()` — `useMutation`, invalidates the history
  query on success.

### New component: `AlignmentHistoryList.tsx`

- Renders paginated rows: document title, course title, run date,
  status — either "Failed: `<error_message>`" (red) or a compact summary
  chip row ("2 match · 1 under · 0 over · 3 not addressed") using the same
  status colors as `AlignmentResultsTable`.
- Standard page/page-size pagination controls, default page size 20,
  matching the existing Documents list pattern.
- Delete icon-button per row → `window.confirm` → `useDeleteAlignmentCheck`
  → if the deleted row was `activeCheckId`, clear it back to the list.
- Row click → sets `activeCheckId` + syncs pickers (handled by the parent
  page, row just calls an `onSelect` prop).

### `AlignmentCheckPage.tsx` changes

- Replace the current "blank until a check runs" body with:
  `activeCheckId ? <results view> : <AlignmentHistoryList onSelect={...} />`.
- Wire `onSelect` to set `activeCheckId` and both picker values.
- On `runCheck` success, set `activeCheckId` and invalidate the history
  query.

## Testing plan

**Backend** (`server/tests/curriculum_map/`):
- `list_alignment_checks`: ownership scoping (only the caller's checks),
  newest-first ordering, pagination boundaries (page 1 vs 2, partial last
  page), empty list for a user with none.
- `delete_alignment_check`: happy path removes the row; 404 for another
  user's check; 404 for a nonexistent/already-deleted check.
- Router tests for both new endpoints mirroring existing patterns in
  `test_router.py` (auth required, 404 mapping, response shape).

**Frontend**:
- Mapping/type tests for the new list response shape, alongside the
  existing `alignmentHelpers.test.ts`.
- `AlignmentHistoryList` component tests: renders rows from mock data,
  pagination controls change page, delete button triggers confirm +
  mutation, row click fires `onSelect` with the right check.

No existing tests change — this is additive only, consistent with every
other task in this module so far.
