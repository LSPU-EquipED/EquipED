# ITSO Review Modal + Per-Evaluation DPO Export Design

Date: 2026-08-11
Branch: `feat/dpo-itso-scoring`
Builds on: `docs/superpowers/specs/2026-08-10-dpo-itso-scoring-design.md`

## Problem

The ITSO-phase DPO feedback loop (per-criterion Accept/Reject/Edit buttons on
the Scorecard, `export_dpo_pairs.py`) is implemented and merged, but two
gaps surfaced during manual review of the built feature:

**UI**: each ITSO criterion row carries 3 buttons (Accept/Reject/Edit),
15 buttons total across 5 criteria. It's cluttered, and treats each
criterion as an independent decision rather than one coherent review of
the evaluation.

**Export correctness**: ITSO scores all 5 criteria in a single LLM call
(`itso/execution.py`), but `export_dpo_pairs()` currently exports one pair
per *edited criterion*, using the shared per-evaluation `prompt_text` paired
against only a fragment of what the model actually generated (one
criterion's `{score, justification}`, not the full 5-criterion response).
This is a category mismatch for DPO, which compares complete responses to
a prompt. Separately, corrections from the same document/reviewer session
aren't independent signal, but nothing distinguishes "50 corrections
across 50 documents" from "50 corrections from one afternoon on 10
documents" — a real risk for judging whether there's "enough" data to
train on.

## Goals

- Replace the 5×3-button Scorecard layout with a single "Review Scores"
  action on the ITSO section that opens a modal covering all 5 criteria
  at once.
- Make `export_dpo_pairs()` produce one pair per *evaluation*, using the
  full 5-criterion response on both the `chosen` and `rejected` side, so
  each pair reflects a response shape the model could actually generate.
- Surface data diversity (distinct evaluations/documents/reviewers) in the
  export script's output so a human deciding whether to train has real
  information, not just a raw pair count.

## Non-goals

- No new backend endpoint. The modal reuses the existing
  `POST /feedback/{evaluation_id}/criteria/{criterion_id}` endpoint,
  firing it once per criterion that actually changed.
- No `PreferenceLog`/database schema changes.
- No change to what `ACCEPT`/`REJECT`/`EDIT` mean at the API level — only
  which of them the new UI actually sends (it never sends `ACCEPT`).
- No automatic training trigger, scheduler, candidate-model registry, or
  promotion UI. That remains explicitly out of scope, per the original
  design doc's Non-goals — this document only touches the review UI and
  the export step.
- No new frontend test infrastructure investment beyond what
  `2026-08-10-dpo-itso-scoring-design.md`'s phase already added.

## Frontend: Scorecard Review Modal

### Current state (being replaced)

`Scorecard.tsx`'s criteria table has a 4th "Reviewer" column; ITSO rows
render `<CriterionFeedbackControls>` (3 buttons: Accept/Reject/Edit,
`client/src/features/evaluation/components/CriterionFeedbackControls.tsx`).
Each button fires an immediate, independent
`useSubmitCriterionFeedback` mutation.

### New design

- Remove the 4th "Reviewer" column and per-row `<CriterionFeedbackControls>`
  entirely from the criteria table.
- Add a single button at the ITSO domain-header row (alongside the
  existing Subtotal/adjectival-rating badges) — e.g. "Review Scores."
- Clicking it opens a modal (new component,
  `client/src/features/evaluation/components/ItsoReviewModal.tsx`)
  listing all 5 ITSO criteria. Each
  criterion shows:
  - The AI's justification, as reference text (read-only).
  - An **editable** score field and justification textarea, pre-filled
    with the AI's current values.
  - A "Flag as incorrect" toggle, for a criterion the reviewer disagrees
    with but doesn't have a replacement value for.
- **Draft-first**: all edits and flags live in the modal's local React
  state. Nothing is submitted until the reviewer clicks one "Submit"
  button at the bottom. Closing the modal without submitting discards the
  draft (matches the existing Edit form's "Cancel" behavior, just scoped
  to all 5 criteria instead of one).
- **On Submit**, per criterion, exactly one of:
  - **Flagged incorrect** → `POST .../criteria/{id}` with `action: "REJECT"`.
  - **Score or justification changed** from the AI's original → `POST
    .../criteria/{id}` with `action: "EDIT"` and the new values.
  - **Untouched, not flagged** → no request sent for that criterion.
    Matches how the export script already treats untouched criteria
    (neutral, not a false endorsement) — see `2026-08-10`'s design doc.
- All resulting requests are fired from the Submit handler (reusing
  `useSubmitCriterionFeedback`, one `mutate()` call per criterion that
  needs one). On success, close the modal; the existing
  `queryClient.invalidateQueries(['evaluation-results', evaluationId])`
  (already wired in the hook) refreshes the Scorecard.
- If one or more submissions fail, surface a visible error (per the
  existing `onError` handling pattern in `CriterionFeedbackControls.tsx`)
  and keep the modal open with the draft intact, so the reviewer doesn't
  lose their work and can retry.

### Backend

No changes. The endpoint, schemas, and `PreferenceLog` table are exactly
as built in the prior phase.

## Export Script: Per-Evaluation Pairing

### Current behavior (being replaced)

`export_dpo_pairs()` in `server/scripts/export_dpo_pairs.py` finds the
latest `EDIT` `PreferenceLog` row per `(evaluation_id, criterion_id)` and
yields one pair per row: `{"prompt": <shared per-evaluation prompt>,
"chosen": <one criterion's corrected {score, justification}>, "rejected":
<that same one criterion's original {score, justification}>}`.

### New behavior

`export_dpo_pairs()` yields one object per *evaluation* instead:

```python
@dataclass(frozen=True)
class DpoPair:
    prompt: str
    chosen: str      # JSON: {"criterion_scores": {criterion_id: {"score": int, "justification": str}, ...}}
    rejected: str     # same shape, AI's original values for every criterion
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    reviewer_ids: frozenset[uuid.UUID]
```

Algorithm:

1. Find the latest `EDIT` `PreferenceLog` row per `(evaluation_id,
   criterion_id)` — same query/dedup as today.
2. Group those by `evaluation_id`:
   `edits_by_evaluation[evaluation_id][criterion_id] = log`.
3. For each `evaluation_id`:
   - Fetch its `AgentResult` (`agent_name="itso"`). If missing or
     `prompt_text` is empty, log a warning naming every grouped
     `PreferenceLog.log_id` and skip the evaluation (same "log, never
     silently drop" principle as before, now applied once per evaluation
     instead of once per criterion).
   - Fetch **all** `CriterionScore` rows for that `AgentResult` (all
     criteria ITSO scored, typically 5) — this is the ground truth for
     the `rejected` side and the fallback for untouched `chosen` slots.
   - For each `CriterionScore` row (`criterion_id` = `cid`):
     - `rejected[cid] = {"score": cid's original score, "justification":
       cid's original justification}` — always.
     - If `cid` has a grouped edit AND it represents a genuine change
       (score or stripped justification differs from the original,
       matching the existing degenerate-edit check) AND `edited_json` is
       non-empty: `chosen[cid] = {"score": edited score, "justification":
       edited justification}`, and add `log.user_id` to this evaluation's
       `reviewer_ids`.
     - Otherwise (no edit, or an edit that's empty/degenerate — log a
       warning for the degenerate/empty case, naming the `log_id`):
       `chosen[cid] = rejected[cid]` (same value on both sides — no
       signal, not a false endorsement).
   - If no `criterion_edits` key was ever consumed by a real
     `CriterionScore` row (e.g. a stray edit referencing a criterion_id
     that doesn't exist for this evaluation), log a warning naming that
     `log_id` — data worth knowing about, even though it can't be used.
   - If `chosen == rejected` across every criterion (no criterion had a
     real correction survive the checks above), log a warning and skip
     the evaluation entirely — same principle as today's single-criterion
     degenerate-pair guard, now applied post-merge.
   - Otherwise, yield the `DpoPair`.

`chunk_ids`/`evidence` fields are intentionally excluded from both
`chosen` and `rejected` — reviewers never edit those, so carrying the
AI's original (possibly stale) evidence citations into what's labeled
`chosen` would reintroduce a smaller version of the stale-justification
problem the degenerate-pair guard already exists to prevent.

### `main()`: diversity reporting

While writing the JSONL (still just `{"prompt", "chosen", "rejected"}`
per line — the `DpoPair`'s `evaluation_id`/`document_id`/`reviewer_ids`
are bookkeeping, not part of the training file), accumulate:

```python
evaluations: set[uuid.UUID] = set()
documents: set[uuid.UUID] = set()
reviewers: set[uuid.UUID] = set()
```

from each yielded `DpoPair`, and after writing, log:

```
Wrote {N} DPO pairs across {len(evaluations)} evaluations,
{len(documents)} documents, {len(reviewers)} reviewers.
```

Pure visibility — no gating logic. Deciding "is this enough / diverse
enough to train on" stays a human judgment call, same as the rest of this
feature's training/deployment stance.

### Format change note

This changes the JSONL output shape from flat
`{"score", "justification"}` per line to nested
`{"criterion_scores": {...}}` per line. Since no training script consumes
this format yet, this is safe to change now rather than needing a
migration or versioned format.

### Operational note (documentation only, no new mechanism)

The export script reads full history every run, not an incremental delta
since the last export. Re-running it after more corrections come in is
safe and expected (each run is a fresh, complete snapshot). What isn't
safe: manually combining the output of two separate export runs into one
training session — since the same evaluation could appear in both runs at
different points of completeness, producing overlapping/redundant
entries. The operational rule is: always train from a single, freshly
generated export, never concatenate multiple export files together. Worth
a comment in the script; no code changes needed to enforce it in this
phase.

## Testing

**Backend** (`server/tests/scripts/test_export_dpo_pairs.py`, rewritten):

- One evaluation, one criterion edited among 5 → pair produced with 1
  changed slot, 4 unchanged slots matching the AI's originals.
- One evaluation, zero real edits (nothing touched, or only
  ACCEPT/REJECT with no EDIT, or an EDIT that's degenerate) → no pair
  produced.
- One evaluation, two different reviewers each editing a different
  criterion → pair produced with both `user_id`s in `reviewer_ids`.
- Missing `prompt_text` / missing `CriterionScore` rows → still skipped
  with a warning, same as today, now evaluated once per evaluation.
- `main()`'s diversity-count log line, given a small multi-evaluation
  fixture set.

**Frontend**: `pnpm lint` + `pnpm build` clean, plus a manual browser
walkthrough of the modal (open, edit some criteria, flag one incorrect,
leave others untouched, submit, confirm only the changed/flagged criteria
produced requests, confirm the Scorecard refreshes) — consistent with how
`CriterionFeedbackControls.tsx` was originally verified, not a new
component-test investment.
