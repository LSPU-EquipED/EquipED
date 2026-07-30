# Curriculum Alignment Pipeline — Design

Date: 2026-07-30
Status: Approved for planning

## 1. Purpose

A new, independent pipeline that checks whether an uploaded SLM aligns with the
learning objectives its course is expected to cover, per an institutional
curriculum map (I = Introductory, E = Enabling, D = Demonstrative, blank = not
applicable to that course).

This is explicitly **not** part of the existing SME/Coordinator/GAD/ITSO
scoring pipeline. It must not modify, extend, or interfere with that pipeline
or its output in any way. It is advisory only, same as every other evaluation
surface in this system — human CID reviewers hold final authority.

## 2. Relationship to existing code

Coordinator's A-05 extension (`server/modules/agents/scoring/curriculum_alignment.py`)
already performs a related but distinct check: a boolean "is this SLM
objective addressed in curriculum text?" judgment against free-text curriculum
content retrieved from Chroma. It has no structured course/objective/level
data and no depth (I/E/D) comparison.

This new pipeline is fully independent of that code path:
- It does not call, wrap, or modify `curriculum_alignment.py` or Coordinator.
- It does not touch `supervisor.py`'s parallel agent dispatch.
- It introduces its own tables, its own service, its own route, and its own
  frontend feature.

A-05 is left exactly as it is today. No deprecation or consolidation is in
scope for this project.

## 3. Data model

New module: `server/modules/curriculum_map/` (models, service, schemas,
seed data) — kept separate from `modules/rubrics/` (criteria/bands-shaped,
not course × objective × level-shaped) and from `modules/agents/`
(orchestration only).

```
courses
  course_id     PK
  course_code   e.g. "IT301"
  course_title  e.g. "Data Structures and Algorithms"
  program       e.g. "BSIT"

curriculum_objectives
  objective_id  PK
  code          e.g. "IT08"
  description   e.g. "Function effectively as an individual and as a
                 member or leader in diverse teams and in multidisciplinary
                 settings."
  program       objectives are program-scoped (e.g. all BSIT PEOs/POs)

curriculum_map_cells
  id            PK
  course_id     FK -> courses
  objective_id  FK -> curriculum_objectives
  level         one of "I", "E", "D"
```

A blank cell in the source curriculum map is represented by the **absence of
a row** in `curriculum_map_cells` for that (course_id, objective_id) pair —
not a stored null. This is what lets the pipeline "ignore blank mappings
entirely" (§6) without any extra filtering logic.

This data is **structured relational data** (exact tabular cells), not
retrieval-context prose, so it belongs in Postgres like the `rubrics` module
does — not in Chroma. This does not conflict with the project's existing
"reference docs only in Chroma" intent, which concerns document-chunk
storage (syllabus/curriculum PDF text), not structured tabular data derived
from those documents.

**Result storage**: a new `curriculum_alignment_checks` table (in the same
module), one row per run:

```
curriculum_alignment_checks
  check_id           PK
  document_id        FK -> documents
  course_id          FK -> courses
  run_at
  model_name
  objective_results  JSON: list of per-objective result objects (§5)
  summary            JSON: counts per status (§5)
  success             bool
  error_message       nullable
```

No foreign key or schema coupling to `evaluations` or any agent-scoring
table. Each run creates a new row (append-only history); re-running a check
for the same document/course never overwrites a prior row.

## 4. Seeding

One-time seed script reading a JSON file, following the existing
`server/data/rubrics/rubrics.json` pattern:

```
server/data/curriculum_map/
  it_program.json   # courses, objectives, and I/E/D cells for the IT program
```

Scope for this phase is the IT program only (the curriculum map already in
hand). No admin CRUD UI for authoring/editing curriculum maps is built now;
adding a new program later means adding a new JSON file and re-running the
seed script.

## 5. Pipeline flow

Triggered on-demand, not as part of the automatic parallel agent dispatch in
`supervisor.py`:

1. User selects an already-uploaded document and a course (see §7, frontend)
   and clicks "Run Curriculum Alignment Check."
2. Service loads:
   - Clean SLM text via the same fitz-extraction source SME's engine uses
     (never joined/overlapping DB chunks — see engine-input discipline
     already established for SME).
   - The course's `curriculum_map_cells` joined with `curriculum_objectives`
     — only rows that exist for this `course_id` (blanks are excluded by
     construction, §3).
3. If the course has zero mapped objectives, short-circuit with an explicit
   "no curriculum map for this course" result (§8) rather than proceeding.
4. One LLM call for the whole set of mapped objectives (never one call per
   objective — this pipeline shares the same token/minute budget as SME,
   Coordinator, GAD, and ITSO). Extraction of the SLM's own stated
   objectives is done independently by this pipeline's own prompt — it does
   not reuse SME's existing objective extraction, so this pipeline never
   depends on a prior SME/Coordinator run having occurred.

   For each mapped objective, the LLM returns:
   ```json
   {
     "objective_code": "IT08",
     "is_addressed": true,
     "observed_level": "I",
     "evidence": "exact quoted SLM text, or null"
   }
   ```
5. Pure `compare()` function (no LLM, no IO — unit-testable in isolation)
   takes the LLM's per-objective output plus the expected levels from the
   map and assigns one of four statuses, using strictness ordering
   `I < E < D`. `is_addressed` is checked first and takes priority over
   whatever `observed_level` the LLM returned:
   - `is_addressed == false` → **not_addressed** (regardless of
     `observed_level` — a not-addressed objective should never carry a
     depth reading)
   - else, `observed_level == expected_level` → **match**
   - else, `observed_level < expected_level` → **under-developed**
     (objective present but shallower than the curriculum requires)
   - else, `observed_level > expected_level` → **over-developed** (deeper
     than required — informational, not necessarily a problem)
6. Persist one `curriculum_alignment_checks` row with the full per-objective
   breakdown and a summary of counts per status.
7. Return the result to the client. Advisory only — no gatekeeping, no
   blocking of any other workflow.

Blank cells (no row in `curriculum_map_cells` for a given course/objective
pair) are never sent to the LLM and never appear in the output at all — they
are not evaluated, not flagged, not mentioned.

## 6. Output shape

```json
{
  "check_id": "uuid",
  "document_id": "uuid",
  "course_id": "uuid",
  "course_title": "Data Structures and Algorithms",
  "run_at": "2026-07-30T00:00:00Z",
  "model_name": "...",
  "objective_results": [
    {
      "code": "IT08",
      "description": "Function effectively as an individual and as a member or leader in diverse teams and in multidisciplinary settings.",
      "expected_level": "D",
      "is_addressed": true,
      "observed_level": "I",
      "status": "under-developed",
      "evidence": "exact quoted SLM text, or null"
    }
  ],
  "summary": {
    "total_mapped_objectives": 9,
    "match": 5,
    "under_developed": 2,
    "over_developed": 1,
    "not_addressed": 1
  },
  "success": true,
  "error_message": null
}
```

## 7. Edge cases and failure handling

| Case | Handling |
|---|---|
| Course has no curriculum map rows at all | Short-circuit with `success: false` and a clear message ("no curriculum map seeded for this course"). Never silently report "0 objectives, all fine." |
| SLM has zero extractable objectives | Early return with a message, same fallback discipline as the existing `evaluate_against_curriculum` function. |
| LLM returns a malformed JSON payload or an objective code that isn't in the requested set | Validate every returned code against the course's actual mapped objective codes; drop/ignore anything that doesn't match (mirrors the `valid_ids` filtering pattern already used in `curriculum_alignment.py`). |
| LLM claims `is_addressed: true` with an evidence quote that isn't actually a substring of the SLM source text | Verify the quote is grounded in the source text; if not found, downgrade that objective to `not_addressed` rather than trusting an ungrounded claim. |
| Selected course has no curriculum map seeded (e.g. non-IT course, before more programs are added) | Same handling as "no curriculum map rows" — explicit "not supported yet" message. |
| Re-running a check for the same document/course | Always inserts a new `curriculum_alignment_checks` row; history is append-only, never overwritten. |
| SLM text exceeds prompt context budget | Reuse the SME engine's existing downsampling/window-sampling strategy for long documents, rather than inventing a new one. |

## 8. Frontend

New feature module `client/src/features/curriculumAlignment/`, following the
same `api/ + components/ + hooks/ + pages/` skeleton every other feature
uses (`evaluation/`, `upload/`, `dashboard/`, etc.).

**Route**: a separate page at `/alignment` (not embedded in the existing
Scorecard page), added as a sibling to `evaluationsRoute`/`matrixRoute`
under `shellRoute` in `client/src/app/router.tsx`. New nav entry in
`client/src/app/layout/Sidebar.tsx`'s `workspaceNavItems`.

**Page** (`AlignmentCheckPage.tsx`):
1. Document picker + a new `CourseSelector.tsx`, a direct clone of
   `shared/components/ProgramSelector.tsx`'s combobox (search, keyboard
   nav, ARIA roles) backed by `courses` instead of programs.
2. Primary "Run Curriculum Alignment Check" button, using the existing
   button convention (`bg-[#1b3b87]`, `rounded-sm`, uppercase label).
3. Results table below, styled like `Scorecard.tsx`'s table: columns
   Objective (code + description) / Expected / Observed / Status badge,
   with a nested evidence-quote box (`bg-slate-50 border-slate-100`,
   same convention as criterion-justification rows) under any row that has
   a quote.
4. Evidence rows support the same click-to-scroll-and-flash pattern already
   used in `DocumentPane.tsx`/`FlagList.tsx`: clicking an evidence quote
   jumps to and briefly highlights the matching text in the SLM reading
   pane, using the same `scrollIntoView` + temporary highlight-class
   mechanism.
5. Loading state: `Loader2` spinner, primary blue, centered — same as every
   other agent's loading state.
6. Empty/error states: same dashed-border (empty) and red-tinted-box
   (error) conventions as `DocumentDashboard.tsx`/`Scorecard.tsx`.

**Status badge colors** — graduated severity, matching the existing
adjectival-rating palette:
- `match` → green `#3b963e`
- `over-developed` → light blue `#3eaed4`
- `under-developed` → gold `#f2c811` (dark text, same treatment as "Needs
  Improvement")
- `not_addressed` → red `#b91c1c`

**New shared code**: `client/src/features/curriculumAlignment/utils/alignmentHelpers.ts`,
parallel to `evaluation/utils/scoreHelpers.ts`, holding the
status → color/label mapping as a single source of truth (avoiding the
duplicated adjectival-color logic that currently exists between
`Scorecard.tsx` and `MonitoringTable.tsx`).

No new shared UI primitives are introduced — everything reuses the existing
hand-rolled Tailwind conventions already established across the app.

## 9. Explicitly out of scope for this phase

- Any change to A-05, Coordinator, SME, GAD, ITSO, or `supervisor.py`.
- Automatic course detection (AI-inferred or fuzzy-matched) — course
  selection is manual only.
- Numeric/banded scoring for this pipeline — output is descriptive only.
- Admin CRUD UI for authoring curriculum maps — seeding is a one-time script
  against a JSON file, IT program only.
- Support for programs other than IT.
- Reusing SME's existing objective extraction — this pipeline extracts SLM
  objectives independently.
