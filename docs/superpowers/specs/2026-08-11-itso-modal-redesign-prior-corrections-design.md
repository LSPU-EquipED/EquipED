# ITSO Review Modal Redesign + Prior-Correction Awareness

Date: 2026-08-11
Branch: `feat/dpo-itso-scoring`
Builds on: `docs/superpowers/specs/2026-08-11-itso-review-modal-and-export-design.md`

## Problem

Manual testing of the ITSO review modal (built in the prior phase) surfaced
two gaps:

1. **Reopening the modal always shows the AI's original score/justification,
   never a reviewer's own prior correction.** `get_evaluation_results`
   builds each criterion purely from `CriterionScore` (the AI's immutable
   original output); it never looks at `PreferenceLog`. So a reviewer who
   corrects a criterion, closes the modal, and reopens it later sees their
   own correction has vanished — the AI's original is back, with no
   indication anything was ever submitted (though the correction is not
   actually lost; it's just invisible in this view).
2. **The modal's visual design and header button are rough.** The "Review
   Scores" button clips inside a fixed-width table cell it shares with the
   adjectival-rating badge, and the modal itself (plain dropdown score
   selector, all 5 justification textareas always visible at once, a
   labeled checkbox for "flag as incorrect") is harder to scan than it
   needs to be.

## Goals

- Surface a reviewer's latest correction (if one exists) when the modal
  reopens, without ever losing track of what the AI actually originally
  said.
- Redesign the modal to be compact by default (5 criteria, AI justification
  as quick reference) and expand only the criterion being worked on, with a
  live running count and subtotal preview.
- Fix the header button's placement so it never clips, regardless of label
  length.

## Non-goals

- No change to the main Scorecard table's displayed score/subtotal/
  adjectival rating — those keep showing the AI's original computation,
  unchanged. This stays a review-modal-only concern (explicit scope
  decision, matches the prior phase's "no self-review-of-official-score"
  posture).
- No new backend endpoint. The prior correction data rides on the existing
  `GET /evaluations/{id}/results` response as one new optional field —
  additive only, every other consumer (PDF export, etc.) is unaffected.
- No change to what `ACCEPT`/`REJECT`/`EDIT` mean at the API level, and no
  "un-reject" action — retracting a REJECT is out of scope here, same as
  the prior phase.
- No new frontend component-test infrastructure, consistent with the
  established convention for this feature area (lint + build + manual
  browser walkthrough).

## Backend: prior-correction data

`get_evaluation_results` (`server/modules/synthesis/service.py`) gains a
lookup of the latest `PreferenceLog` row per `(evaluation_id, criterion_id)`
for `agent_name="itso"` (same "latest wins" rule the export script already
uses), and attaches it to each ITSO criterion in the response:

```python
reviewer_correction: {
    "action": "EDIT" | "REJECT",
    "score": int | None,       # present only for EDIT
    "justification": str | None,  # present only for EDIT
} | None
```

`None` when no `PreferenceLog` row exists for that criterion. This is a
straightforward read-only join alongside the existing `CriterionScore`
query already in that function — no new query pattern, just one more
lookup keyed the same way the export script already keys its own lookups.

`CriterionScoreItem` (frontend type, `client/src/features/evaluation/types.ts`)
gains the matching optional field.

## Modal: data model

On open, each criterion's **baseline** is: its `reviewer_correction` if one
exists and `action === "EDIT"`, else the AI's original `{score,
justification}`. A `REJECT`-only `reviewer_correction` does not change the
score/justification baseline (REJECT never carries a replacement value,
per the prior phase's design) — but it does mean the criterion opens with
"Flag as incorrect" already active.

- The header's "N of 5 edited" count and the live subtotal preview are
  computed from baselines (not always from the AI original) — so a
  criterion with a prior correction counts as "edited" even before the
  reviewer touches anything in this session.
- The "did this criterion change" check (used for Submit and for the
  "edited" badge) compares the current draft against *that criterion's
  baseline*, not always the raw AI original. This is load-bearing: without
  it, reopening a previously-corrected criterion and clicking Save changes
  without touching it would look like a "change" (baseline ≠ AI original)
  and silently create a duplicate no-op EDIT every time.
- **Revert** always resets to the true AI original — regardless of whether
  a prior correction existed — and collapses the criterion back to its
  compact, read-only display. The "AI scored X — {original justification}"
  hint text always names the true original, never a prior correction.

## Modal: visual/interaction redesign

- **Header**: "Review ITSO Scores" title, close (×) button, and a live
  subtitle: `"{N} of 5 edited · subtotal {avg}/4"`. The subtotal is
  recomputed client-side as a simple average of the 5 current draft scores
  (matches the real backend formula — `AgentResult.subtotal` is computed
  the same way, `sum(scores)/len(scores)` — confirmed in
  `server/modules/agents/itso/execution.py`).
- **Each criterion, compact by default**: title, AI's justification shown
  as plain reference text (read-only), a row of 4 score buttons (`1 2 3
  4`), and a small flag icon for "flag as incorrect."
  - Score buttons are color-coded by value when unedited (matching the
    existing app-wide convention: low scores red, satisfactory/very
    satisfactory scores green) — except the currently-selected button on
    an **edited** criterion always renders **blue**, signaling "you
    changed this" regardless of the value's normal color.
  - The flag icon gets a red border when active (this criterion is
    flagged incorrect).
- **Each criterion's expanded/collapsed state is independent** — this is
  not an accordion. Any number of criteria can be expanded at once (e.g.
  two already have prior corrections and are pre-expanded, and the
  reviewer additionally clicks into a third).
- **A criterion with an existing correction, or one the reviewer clicks a
  score button on, expands** to show:
  - An "edited" badge next to the title.
  - A **"Justification"**-labeled, editable textarea, pre-filled with the
    baseline (prior correction if one exists, else the AI's original) —
    the explicit label is a deliberate deviation from the visual
    reference, which omits it; keeping it because dropping the label was
    never actually requested, only the reference's overall layout was.
  - A hint line: `"AI scored {original_score}/4 — {original_justification}.
    Revert"` — `Revert` is a clickable link performing the reset described
    above.
- **Flagging a criterion incorrect** collapses/disables its score-button
  and justification interaction (mutually exclusive with editing, same as
  the prior phase — a criterion is either being corrected or flagged, not
  both).
- **Footer**: `"{N} flagged · {M} edited"` summary, "Cancel" / "Save
  changes" buttons (renamed from "Submit" — cosmetic only, same submit
  logic as before: `Promise.allSettled` across whichever criteria actually
  changed, visible error + draft preserved on partial failure, the
  empty-justification guard from the prior fix wave carried forward
  unchanged).

## Header button placement fix

The domain-header row's Status/badge cell is a fixed `w-[10rem]` column —
too narrow to hold both the adjectival badge and the button, which is why
it clips today. The domain-label cell (`"INNOVATION AND IP (ITSO)"`) has
**no width constraint** and is the one column that absorbs all the table's
leftover space, so it has genuine room. Move the "Review Scores" button
into that cell, next to the label (only rendered when `domain === 'itso'`),
and revert the Status cell to just the badge, unchanged for every domain.
This also means every non-ITSO row's layout is completely unaffected.

## Testing

**Backend**: extend `server/tests/synthesis` coverage (or add a focused
test near `get_evaluation_results`) confirming: a criterion with no
`PreferenceLog` row gets `reviewer_correction: None`; a criterion with an
`EDIT` row gets the latest edit's score/justification; a criterion with
only a `REJECT` row gets `{"action": "REJECT", "score": None,
"justification": None}`; multiple `PreferenceLog` rows for the same
criterion resolve to the latest by `created_at`.

**Frontend**: no new component tests (consistent with this feature area's
established convention) — verify via `pnpm lint` + `pnpm build` + a manual
browser walkthrough covering: a criterion with a prior correction opens
pre-expanded showing that correction, not the AI original; the header/
footer counts and live subtotal reflect baselines correctly on open;
clicking a score button expands a previously-compact criterion; Revert
resets to the true AI original and collapses; submitting with zero new
changes on an already-corrected-but-untouched criterion sends zero
requests for it; the header button no longer clips at any adjectival-
rating badge width.
