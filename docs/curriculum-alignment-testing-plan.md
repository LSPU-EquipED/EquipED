# Curriculum Alignment Pipeline — Summary & Testing Plan

Branch: `feat/curriculum-alignment-pipeline` (not merged — for manual testing first)

## ⚠️ Open issue as of end of last session

Running a real check against the live LLM (Groq, `llama-3.1-8b-instant`) was
still producing **"The alignment check could not complete (LLM error or
invalid response)."** A first root cause was found and fixed (see "Session 2
fixes" below — the request was too large for the provider, HTTP 413), but
the error persisted after that fix on a retry, and the session ended before
a fresh log capture could confirm whether it's the same 413 recurring at a
still-too-high budget, or a different failure. **Start next session here:**

1. Make sure the backend server is running (see Setup below).
2. Retry a check from the browser.
3. Read the fresh error from the backend console/log — search for
   `Curriculum alignment LLM check failed:` — that line has the real
   underlying exception message.
4. If it's still HTTP 413: the budget in `service.py`'s `_MAX_SLM_TEXT_CHARS`
   (currently 6000) needs to go lower still, or `max_new_tokens` in
   `alignment_check.py` (currently 1200) needs to shrink further. Compute:
   `len(PROMPT template) + len(objectives JSON for the course) + SLM text
   budget`, roughly ÷4 for a token estimate, and check that + max_new_tokens
   stays comfortably under this model's actual context window (check Groq's
   docs for `llama-3.1-8b-instant`'s real limit — it may be smaller than
   assumed).
5. If it's a different error (timeout, auth, malformed JSON from the model,
   etc.) — that's a new bug, not a recurrence of the budget issue.

## What was built

A new, fully independent pipeline that checks whether an uploaded SLM aligns
with its course's curriculum map (I = Introductory, E = Enabling,
D = Demonstrative per learning objective). It does not modify, call, or share
any code/tables with the existing SME/Coordinator/GAD/ITSO scoring pipeline.

**Backend** — new module `server/modules/curriculum_map/`:
- 4 new tables: `courses`, `curriculum_objectives`, `curriculum_map_cells`,
  `curriculum_alignment_checks` (migration `20260730_0001`).
- Pure I/E/D comparison logic, per-page SLM text extraction with evidence
  grounding (an LLM's claimed quote must literally appear in the SLM text or
  it's downgraded to "not addressed"), a single LLM call per run covering
  every mapped objective at once, and a service layer wiring it together.
- Real seed data: 27 BSIT courses × 12 program outcomes (IT01–IT12),
  transcribed from the official LSPU curriculum mapping form you provided
  (`server/data/curriculum_map/it_program.json`). Note: the form has an
  IT13 column, but its official description text wasn't available, so it's
  intentionally excluded — add it later as a new objective + re-seed once
  you have the text.
- 4 endpoints under `/curriculum-map`: list courses, run a check, get a
  check's result, get a check's document pages.

**Frontend** — new feature `client/src/features/curriculumAlignment/`:
- A new "Curriculum Alignment" page at `/alignment` (new sidebar entry),
  with a document + course picker, a results table (status badges:
  green=match, blue=over-developed, gold=under-developed, red=not-addressed),
  and a split-pane reading view — click an evidence quote and it scrolls to
  and highlights the matching page in the SLM.

**Security fix applied after final review** (commit `7784a34`): the initial
implementation let any logged-in user run a check against *any* document ID,
including other users' SLMs, and read back the full extracted text. This is
now fixed — every endpoint checks that the requesting user actually owns the
document, matching this codebase's existing "SLMs are owner-only" rule.
Also fixed in that same pass: a check that failed (bad PDF, LLM error) no
longer gets silently recorded as "every objective failed" — it's now marked
`success: false` with a clear error message; the LLM can no longer report a
made-up depth level outside I/E/D; and long SLMs are now sampled from both
the start *and* end of the document (not just the start), since real
assessment content usually sits at the bottom of an SLM.

**Test status:** 48/48 backend tests passing, 90/90 frontend tests passing,
full existing backend suite re-run with zero new regressions (same 5
pre-existing, unrelated failures as before this branch existed).

## Session 2: what manual testing found and fixed

The plan above was written before this feature had ever touched a real
database or a real browser. Once it was, manual testing found three real
bugs that no automated test caught, all now fixed and committed:

1. **Seed script path bug** (commit `f8aa0f4`): `python -m
   server.scripts.seed_curriculum_map` failed with `FileNotFoundError` —
   the script's `main()` built its JSON path one directory too shallow.
   Every existing test passed anyway because they all call the inner
   `seed_curriculum_map()` function directly with an already-loaded payload,
   never exercising `main()`'s path logic. Fixed, with a regression test
   added. Confirmed working against a real Postgres DB: migration applied
   cleanly, seed ran and is idempotent (27 courses / 12 objectives / 172
   cells, verified by direct query after seeding twice).
2. **Misleading error display** (commit `aa3c78f`): when the backend
   returns a "soft failure" (HTTP 201 with `success: false` and a real
   `error_message` — the failure-masking fix from the final review),
   the frontend was rendering it through the results table's generic
   empty-state text ("No mapped objectives for this course") instead of
   an actual error box. Fixed — the page now checks `success` and shows
   `error_message` properly.
3. **LLM request too large** (commit not yet made / uncommitted at session
   end — see "Open issue" above): a real check against the live LLM hit
   HTTP 413 from Groq for `llama-3.1-8b-instant` — the prompt (SLM text +
   up to 12 objective descriptions + template) plus the requested 1800-token
   completion exceeded the provider's per-request limit. Reduced
   `_MAX_SLM_TEXT_CHARS` from 20000→6000 and `max_new_tokens` from
   1800→1200 in an attempt to fix it — **this was not yet confirmed working
   before the session ended.**

## Known gaps (not blocking, but worth knowing before/while testing)

- Evidence-quote matching requires an exact substring match against the raw
  PDF text. If the LLM paraphrases whitespace slightly, a real match can be
  missed and get reported as "not addressed" even though the SLM does cover
  it — if you see a course you know is well-covered come back mostly red,
  this is the likely cause, not a broken feature.
- No caching on the document-pages endpoint — it re-extracts the PDF text
  on every request. Fine at current scale.
- `useAlignmentCheck` hook exists but isn't wired into the page yet (a
  result currently only lives in the button's mutation state — refreshing
  the page loses the displayed result, though it's still saved in the DB
  and could be reloaded by check ID later).

## Testing plan (run on your real dev environment, with a real database)

### 0. Setup
```bash
cd path/to/EquipED
git fetch
git checkout feat/curriculum-alignment-pipeline   # or merge it into a test branch first
uv sync --project server
cd client && pnpm install && cd ..
```

### 1. Apply the migration
```bash
uv run --project server alembic upgrade head
```
Confirm it creates `courses`, `curriculum_objectives`, `curriculum_map_cells`,
`curriculum_alignment_checks` with no errors. This is the first time this
migration runs against a real Postgres instance (only tested against
in-memory sqlite so far) — if anything about `sa.Uuid`/`sa.JSON` column
types behaves differently on real Postgres, this is where it'd show up.

### 2. Seed the real curriculum data
```bash
uv run --project server python -m server.scripts.seed_curriculum_map
```
Expected output: `Seeded curriculum map for program BSIT.`
Re-run it a second time — it should print the same message and NOT create
duplicate rows (idempotency).

### 3. Start both servers
```bash
uv run --project server uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```
```bash
cd client && pnpm dev
```

### 4. Log in and check the courses loaded
- Open the app, log in.
- Navigate to **Curriculum Alignment** in the sidebar (new nav item).
- Open the course dropdown — you should see all 27 BSIT courses (e.g.
  "IT-INTRO — Introduction to Information Technology Computing",
  "IT-CAPSTONE — Capstone Project", etc.), searchable by code or title.

### 5. Run a real check
- Pick an already-uploaded SLM document and a course.
- Click "Run Curriculum Alignment Check."
- Confirm: a loading spinner appears, then a results table with one row per
  mapped objective for that course (Expected / Observed / Status columns),
  and the reading pane on the left shows the SLM's pages.
- Click an evidence quote in a row that has one — confirm the reading pane
  scrolls to and briefly highlights the matching page.

### 6. Test the ownership fix (the Critical security fix)
This is the most important thing to verify manually, since it can't be
tested without real multi-user data:
- As User A, upload an SLM (or use an existing one you own).
- Log in as a **different** user, User B.
- Try to trigger a check against User A's document ID (e.g. by directly
  calling `POST /api/v1/curriculum-map/checks` with that document's UUID,
  or by manipulating the document picker if it lists documents you don't
  own — it currently lists via `documentsApi.listDocuments`, which may or
  may not already scope to owned documents depending on other parts of the
  app; check what the dropdown actually shows for User B).
- **Expected:** a 404, not a successful check, and definitely not the SLM's
  text coming back in the response.

### 7. Test the "no curriculum map" failure path
- Pick a course/document combination where the course has no curriculum map
  rows (any course not in the seeded 27, if you have other courses in your
  system) — or temporarily point at a course code that doesn't exist.
- **Expected:** a clear error message, not a blank "0 objectives, all fine"
  result and not a crash.

### 8. Test a long SLM (validates the head+tail sampling fix)
- Upload or pick an SLM whose extracted text is long enough to exceed
  ~20,000 characters (a lecture-heavy module with several units).
- Run a check against a course where you'd expect a "Demonstrative"-level
  objective (e.g. Capstone Project, which maps every objective to D).
- **Expected:** objectives tied to the SLM's actual performance
  tasks/assessments (usually near the end of the document) should be able
  to register as addressed/deeper, not systematically read as shallow just
  because the SLM is long.

### 9. General regression check
- Confirm the existing SME/Coordinator/GAD/ITSO evaluation flow still works
  exactly as before — this feature should have touched none of that code.

## If something breaks

- Backend errors: check the uvicorn console output.
- Frontend errors: check the browser console + Network tab for the failing
  `/api/v1/curriculum-map/*` request.
- Full test suites to re-run if you suspect something: `uv run --project
  server pytest server/tests/curriculum_map/ -v` (backend) and `cd client
  && pnpm test` (frontend).

## When you're ready to merge

Don't merge yet per your instruction — once you've run through this plan,
let me know what you find (or what needs fixing) and I'll take it from there.
