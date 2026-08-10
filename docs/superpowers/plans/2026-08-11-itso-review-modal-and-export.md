# ITSO Review Modal + Per-Evaluation Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Scorecard's 15-button (5 criteria × 3 actions) ITSO review UI with a single "Review Scores" modal covering all 5 criteria at once, and rework the DPO export script to pair the AI's full 5-criterion response against the reviewer's corrected version instead of exporting isolated per-criterion fragments.

**Architecture:** Frontend: one new modal component with draft-first local state, submitted via the existing per-criterion feedback endpoint (no new backend routes). Backend: `export_dpo_pairs()` regroups feedback by evaluation instead of by criterion, merging each evaluation's full set of `CriterionScore` rows with any real corrections into one `chosen`/`rejected` pair, and `main()` reports data diversity (distinct evaluations/documents/reviewers) alongside the pair count.

**Tech Stack:** React 18 + TanStack Query (frontend), Python 3.12 + SQLAlchemy (backend), same stack as the prior ITSO DPO phase.

## Global Constraints

- Frontend: TypeScript, ESLint (react-hooks, react-refresh) + Prettier. No shadcn/ui or external component kits — components are custom-built with Tailwind utility classes, matching the existing style in `CriterionFeedbackControls.tsx`/`Scorecard.tsx`.
- Backend: ruff-enforced (E, F, I, UP), line length 88, Python 3.12.
- No new backend endpoints, no `PreferenceLog`/database schema changes.
- No new frontend component-test infrastructure — this codebase has minimal component-test coverage; verify via `pnpm lint` + `pnpm build` + manual browser walkthrough, per `docs/superpowers/specs/2026-08-11-itso-review-modal-and-export-design.md`'s Testing section.
- Run backend commands from the repo root with `--project server` (e.g. `uv run --project server pytest`), never from inside `server/`. Frontend commands run from `client/`.

---

### Task 1: `ItsoReviewModal` component

**Files:**
- Create: `client/src/features/evaluation/components/ItsoReviewModal.tsx`

**Interfaces:**
- Consumes: `useSubmitCriterionFeedback` (existing,
  `client/src/features/evaluation/hooks/useSubmitFeedback.ts`) — `mutateAsync({criterionId, body: {agent_name, action, score?, justification?}})`.
  `CriterionScoreItem` (existing, `client/src/features/evaluation/types.ts`)
  — `{criterion_id, criterion_text, score, justification, ...}`.
- Produces: `ItsoReviewModal({evaluationId, criteria, onClose})` — Task 2
  imports and conditionally mounts this component directly (the parent
  controls mounting; this component has no internal `open` prop — see
  rationale below).

- [ ] **Step 1: Create the component**

Create `client/src/features/evaluation/components/ItsoReviewModal.tsx`:

```tsx
import { useState } from 'react';
import { X } from 'lucide-react';
import { useSubmitCriterionFeedback } from '../hooks/useSubmitFeedback';
import type { CriterionScoreItem } from '../types';

type CriterionDraft = {
  score: number;
  justification: string;
  rejected: boolean;
};

type ItsoReviewModalProps = {
  readonly evaluationId: string;
  readonly criteria: readonly CriterionScoreItem[];
  readonly onClose: () => void;
};

function initialDrafts(
  criteria: readonly CriterionScoreItem[],
): Record<string, CriterionDraft> {
  return Object.fromEntries(
    criteria.map((c) => [
      c.criterion_id,
      { score: c.score, justification: c.justification, rejected: false },
    ]),
  );
}

export function ItsoReviewModal({ evaluationId, criteria, onClose }: ItsoReviewModalProps) {
  const [drafts, setDrafts] = useState<Record<string, CriterionDraft>>(() =>
    initialDrafts(criteria),
  );
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const mutation = useSubmitCriterionFeedback(evaluationId);

  function updateDraft(criterionId: string, patch: Partial<CriterionDraft>) {
    setDrafts((prev) => ({ ...prev, [criterionId]: { ...prev[criterionId], ...patch } }));
  }

  async function handleSubmit() {
    setSubmitError(null);

    const actions = criteria
      .map((criterion) => {
        const draft = drafts[criterion.criterion_id];
        if (draft.rejected) {
          return {
            criterionId: criterion.criterion_id,
            body: { agent_name: 'itso' as const, action: 'REJECT' as const },
          };
        }
        const scoreChanged = draft.score !== criterion.score;
        const justificationChanged =
          draft.justification.trim() !== criterion.justification.trim();
        if (scoreChanged || justificationChanged) {
          return {
            criterionId: criterion.criterion_id,
            body: {
              agent_name: 'itso' as const,
              action: 'EDIT' as const,
              score: draft.score,
              justification: draft.justification,
            },
          };
        }
        return null;
      })
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null);

    if (actions.length === 0) {
      onClose();
      return;
    }

    setIsSubmitting(true);
    // Retry-all on partial failure: PreferenceLog is append-only and the
    // exporter dedups to the latest edit per criterion, so re-sending an
    // already-succeeded action on retry is harmless, not a duplicate bug.
    const results = await Promise.allSettled(
      actions.map((entry) => mutation.mutateAsync(entry)),
    );
    setIsSubmitting(false);

    if (results.some((result) => result.status === 'rejected')) {
      setSubmitError("Some corrections couldn't be saved. Please try again.");
      return;
    }

    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-sm border border-slate-200 bg-white shadow-lg">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Review ITSO Scores
          </h2>
          <button
            type="button"
            title="Close"
            className="inline-flex size-7 items-center justify-center rounded-sm text-slate-400 hover:bg-slate-50 hover:text-slate-600"
            onClick={onClose}
            disabled={isSubmitting}
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="grid gap-4 px-5 py-4">
          {criteria.map((criterion) => {
            const draft = drafts[criterion.criterion_id];
            return (
              <div
                key={criterion.criterion_id}
                className="grid gap-2 rounded-sm border border-slate-200 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-800">
                    {criterion.criterion_text}
                  </div>
                  <label className="flex shrink-0 items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#b91c1c]">
                    <input
                      type="checkbox"
                      checked={draft.rejected}
                      onChange={(event) =>
                        updateDraft(criterion.criterion_id, { rejected: event.target.checked })
                      }
                    />
                    Flag as incorrect
                  </label>
                </div>
                <p className="text-xs leading-relaxed text-slate-500">
                  AI justification: {criterion.justification}
                </p>
                <div className="grid grid-cols-[5rem_1fr] gap-2">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Score
                    <select
                      className="mt-1 block w-full rounded-sm border border-slate-200 px-2 py-1 text-xs disabled:bg-slate-50 disabled:text-slate-400"
                      value={draft.score}
                      disabled={draft.rejected}
                      onChange={(event) =>
                        updateDraft(criterion.criterion_id, { score: Number(event.target.value) })
                      }
                    >
                      {[1, 2, 3, 4].map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Justification
                    <textarea
                      className="mt-1 block w-full rounded-sm border border-slate-200 px-2 py-1 text-xs disabled:bg-slate-50 disabled:text-slate-400"
                      rows={2}
                      value={draft.justification}
                      disabled={draft.rejected}
                      onChange={(event) =>
                        updateDraft(criterion.criterion_id, { justification: event.target.value })
                      }
                    />
                  </label>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-slate-200 px-5 py-4">
          {submitError ? (
            <p className="text-[10px] font-semibold text-[#b91c1c]">{submitError}</p>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-sm border border-slate-200 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-500"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="button"
              className="rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#1b3b87] disabled:opacity-50"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Submitting…' : 'Submit'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Why no internal `open` prop:** Task 2's parent will conditionally *mount*
this component (`{isItsoReviewOpen && <ItsoReviewModal ... />}`) rather
than always rendering it with a visibility flag. This matters: if the
component instead stayed mounted with an `open` prop toggling visibility,
`useState(() => initialDrafts(criteria))`'s lazy initializer would only
run once on first mount — reopening the modal later (after the Scorecard
refetched with different AI values) would show stale drafts from the
first time it ever opened. Conditional mounting gives a fresh component
instance, and therefore fresh drafts, every time it opens.

- [ ] **Step 2: Lint and typecheck**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors. (The component isn't wired into the app yet — Task 2
does that — so `pnpm build` here only confirms this file itself is valid
TypeScript/JSX with no unused-import or type errors.)

- [ ] **Step 3: Commit**

```bash
git add client/src/features/evaluation/components/ItsoReviewModal.tsx
git commit -m "feat(evaluation): add ITSO review modal component"
```

---

### Task 2: Wire the modal into the Scorecard, remove the old per-row controls

**Files:**
- Modify: `client/src/features/evaluation/components/Scorecard.tsx`
- Delete: `client/src/features/evaluation/components/CriterionFeedbackControls.tsx`

**Interfaces:**
- Consumes: `ItsoReviewModal` from Task 1 — `{evaluationId, criteria, onClose}`.
- Produces: nothing new — this is the last consumer-facing task for the UI
  side; nothing later depends on `Scorecard.tsx`'s internals.

- [ ] **Step 1: Update imports and add modal-open state**

In `client/src/features/evaluation/components/Scorecard.tsx`, change the
imports (currently lines 1-10):

```tsx
import { Fragment, useMemo, useState } from 'react';
import { Outlet, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Loader2, CheckCircle, Flag, FileText, Clock } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import { useEvaluation } from '../hooks/useEvaluationStatus';
import { evaluationApi } from '../api/evaluation.api';
import { formatScore, cleanJustification, overallScoreDisplay } from '../utils/scoreHelpers';
import { ScorecardPdfExport } from './ScorecardPdfExport';
import { ItsoReviewModal } from './ItsoReviewModal';
```

(only two changes: `useState` added to the `react` import; the
`CriterionFeedbackControls` import replaced with `ItsoReviewModal`.)

Inside `export function Scorecard() {`, right after the existing
`const { data: evaluation, ... } = useEvaluation(id ?? '');` line, add:

```tsx
  const [isItsoReviewOpen, setIsItsoReviewOpen] = useState(false);
```

- [ ] **Step 2: Remove the "Reviewer" table column header**

Find the `<thead>` block (currently):

```tsx
                <thead className="bg-slate-50 border-b border-slate-200 select-none">
                  <tr>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-slate-500">
                      Evaluation Criterion & Justification
                    </th>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-slate-500 w-[6rem] text-right">
                      Score
                    </th>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-slate-500 w-[10rem]">
                      Status
                    </th>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-slate-500 w-[9rem]">
                      Reviewer
                    </th>
                  </tr>
                </thead>
```

Remove the last `<th>...Reviewer</th>` block, leaving 3 `<th>`s.

- [ ] **Step 3: Revert the SKIPPED row's `colSpan`**

Find `<td colSpan={4} className="py-4 px-4">` (in the `isSkipped` branch)
and change it back to `<td colSpan={3} className="py-4 px-4">` — the
table is back to 3 columns.

- [ ] **Step 4: Move the review button into the domain-header row, remove its old 4th cell**

Find the "Domain Group Header Row" block (currently):

```tsx
                        <tr className="bg-slate-50/60 select-none">
                          <td className="py-3 px-4 text-[10px] font-extrabold text-slate-800 uppercase tracking-widest border-t border-slate-200">
                            {agentLabels[domain]}
                          </td>
                          <td className="py-3 px-4 text-right w-[6rem] border-t border-slate-200">
                            <span className="text-xs font-bold text-slate-500">
                              Subtotal: {formatScore(domainData.subtotal)}/{formatScore(domainData.max_score)}
                            </span>
                          </td>
                          <td className="py-3 px-4 w-[10rem] border-t border-slate-200">
                            {domainData.adjectival_rating && (
                              <span className={cn(
                                'inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                                getAdjectivalRatingClasses(domainData.adjectival_rating)
                              )}>
                                {domainData.adjectival_rating}
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 w-[9rem] border-t border-slate-200" />
                        </tr>
```

Replace it with (3 `<td>`s; the "Review Scores" button now lives inside
the 3rd cell, next to the adjectival badge, only for `domain === 'itso'`):

```tsx
                        <tr className="bg-slate-50/60 select-none">
                          <td className="py-3 px-4 text-[10px] font-extrabold text-slate-800 uppercase tracking-widest border-t border-slate-200">
                            {agentLabels[domain]}
                          </td>
                          <td className="py-3 px-4 text-right w-[6rem] border-t border-slate-200">
                            <span className="text-xs font-bold text-slate-500">
                              Subtotal: {formatScore(domainData.subtotal)}/{formatScore(domainData.max_score)}
                            </span>
                          </td>
                          <td className="py-3 px-4 w-[10rem] border-t border-slate-200">
                            <div className="flex items-center justify-between gap-2">
                              {domainData.adjectival_rating && (
                                <span className={cn(
                                  'inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                                  getAdjectivalRatingClasses(domainData.adjectival_rating)
                                )}>
                                  {domainData.adjectival_rating}
                                </span>
                              )}
                              {domain === 'itso' && (
                                <button
                                  type="button"
                                  className="shrink-0 rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-[#1b3b87] hover:bg-[#1b3b87]/10"
                                  onClick={() => setIsItsoReviewOpen(true)}
                                >
                                  Review Scores
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
```

- [ ] **Step 5: Remove the per-criterion 4th cell**

Find the criterion-detail row's 4th `<td>` (currently):

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

Delete this whole `<td>` block. The criterion-detail `<tr>` now has 3
`<td>`s (Criterion & Justification, Score, Status), matching the header.

- [ ] **Step 6: Render the modal**

Find where the "Structured Criteria Ledger Table" `<div>` closes (right
before the outer `results && (<div className="mx-auto max-w-[90rem] space-y-6">...`
block's own closing `</div>`), and add the modal as a sibling right after
the table's closing `</div>`:

```tsx
            </div>

            {isItsoReviewOpen && results.domain_scores.itso && (
              <ItsoReviewModal
                evaluationId={evaluation.evaluation_id}
                criteria={results.domain_scores.itso.criteria}
                onClose={() => setIsItsoReviewOpen(false)}
              />
            )}
          </div>
        )}
```

(the first `</div>` closes the table container that was already there;
the modal block is new; the final `</div>` and `)}` close the outer
`results && (...)` wrapper, also already there — only the modal block in
the middle is new.)

- [ ] **Step 7: Delete the now-unused component**

`CriterionFeedbackControls.tsx` is no longer rendered anywhere after this
change.

```bash
rm client/src/features/evaluation/components/CriterionFeedbackControls.tsx
```

- [ ] **Step 8: Lint and typecheck**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors, no unused-import warnings (confirms the deleted
component isn't referenced anywhere else — if `pnpm build` fails with a
missing-module error, something still imports the deleted file; find and
update it).

- [ ] **Step 9: Manual verification in the browser**

Run: `cd client && pnpm dev`, navigate to a completed evaluation's
Scorecard. Confirm:
- The criteria table has 3 columns again (no "Reviewer" column).
- Only the ITSO domain-header row shows a "Review Scores" button; SME/
  Coordinator/GAD header rows do not.
- Clicking "Review Scores" opens a modal listing all 5 ITSO criteria,
  each pre-filled with the AI's current score/justification.
- Editing one criterion's score/justification and leaving the rest
  untouched, then clicking Submit: only one `POST
  /api/v1/feedback/{evaluation_id}/criteria/{criterion_id}` request
  fires (Network tab), with `action: "EDIT"`.
- Checking "Flag as incorrect" on a criterion disables its score/
  justification fields; submitting fires that criterion as
  `action: "REJECT"`.
- Leaving every criterion untouched and clicking Submit closes the modal
  immediately with zero requests fired.
- Reopening the modal after a previous submission shows the *current*
  (possibly just-updated) AI values, not stale data from the first time
  it was opened.

- [ ] **Step 10: Commit**

```bash
git add client/src/features/evaluation/components/Scorecard.tsx
git rm client/src/features/evaluation/components/CriterionFeedbackControls.tsx
git commit -m "feat(evaluation): replace per-row ITSO controls with a review modal"
```

---

### Task 3: Per-evaluation DPO pairing + diversity reporting

**Files:**
- Modify: `server/scripts/export_dpo_pairs.py`
- Modify: `server/tests/scripts/test_export_dpo_pairs.py`
- Modify: `server/tests/scripts/conftest.py`

**Interfaces:**
- Consumes: `PreferenceLog`, `AgentResult`, `CriterionScore` (existing,
  unchanged schemas).
- Produces: `export_dpo_pairs(db) -> Iterator[DpoPair]` (changed return
  type — was `Iterator[dict[str, str]]`) and the `DpoPair` dataclass
  itself (`prompt: str`, `chosen: str`, `rejected: str`,
  `evaluation_id`, `document_id`, `reviewer_ids: frozenset`). This is a
  breaking change to the export script's public function signature — no
  other code in this repo calls `export_dpo_pairs()` except `main()` in
  the same file and this task's own tests, both updated here.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `server/tests/scripts/test_export_dpo_pairs.py`:

```python
"""DPO pair export: builds one training pair per evaluation from EDIT feedback."""

from __future__ import annotations

import json
import logging
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


def _seed_evaluation(db_session, *, user_id, criteria=None):
    """Seed one evaluation with an ITSO AgentResult and the given criteria.

    `criteria` defaults to 3 criteria, each with a distinct original
    score/justification, to exercise merging across multiple criteria per
    evaluation.
    """
    if criteria is None:
        criteria = [
            ("itso-01", 4, "No plagiarism detected."),
            ("itso-02", 3, "Bibliography section found with 5 entries."),
            ("itso-03", 2, "No student data confidentiality statement found."),
        ]

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

    for criterion_id, score, justification in criteria:
        db_session.add(
            CriterionScore(
                agent_result_id=agent_result.agent_result_id,
                evaluation_id=job.evaluation_id,
                document_id=document_id,
                criterion_id=criterion_id,
                criterion_title=criterion_id,
                score=score,
                justification=justification,
            )
        )
    db_session.commit()
    return job


def test_export_merges_one_edit_into_full_evaluation_response(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-02",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="In-text citations sufficient; no separate bibliography required.",
    )

    pairs = list(export_dpo_pairs(db_session))

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.prompt == '{"agent": "itso", "document_chunks": []}'
    chosen = json.loads(pair.chosen)["criterion_scores"]
    rejected = json.loads(pair.rejected)["criterion_scores"]

    assert chosen["itso-02"] == {
        "score": 4,
        "justification": "In-text citations sufficient; no separate bibliography required.",
    }
    assert rejected["itso-02"] == {
        "score": 3,
        "justification": "Bibliography section found with 5 entries.",
    }
    for cid in ("itso-01", "itso-03"):
        assert chosen[cid] == rejected[cid]
    assert set(chosen) == {"itso-01", "itso-02", "itso-03"}
    assert pair.reviewer_ids == frozenset({admin_user.user_id})


def test_export_skips_evaluation_with_no_real_edit(db_session, admin_user):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="ACCEPT",
        user_id=admin_user.user_id,
        user_role="admin",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-02",
        agent_name="itso",
        action="REJECT",
        user_id=admin_user.user_id,
        user_role="admin",
    )

    assert list(export_dpo_pairs(db_session)) == []


def test_export_skips_evaluation_where_only_edit_is_degenerate(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=4,
        justification="No plagiarism detected.",
    )

    pairs = list(export_dpo_pairs(db_session))
    assert pairs == []
    assert "no criterion had a real correction survive" in caplog.text


def test_export_tracks_multiple_reviewers_on_one_evaluation(
    db_session, admin_user, faculty_user
):
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="Minor concern noted, not disqualifying.",
    )
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="EDIT",
        user_id=faculty_user.user_id,
        user_role="admin",
        score=4,
        justification="Confidentiality addressed in section 2.",
    )

    pairs = list(export_dpo_pairs(db_session))

    assert len(pairs) == 1
    assert pairs[0].reviewer_ids == frozenset({admin_user.user_id, faculty_user.user_id})


def test_export_skips_evaluation_missing_prompt_snapshot(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    db_session.query(AgentResult).filter_by(evaluation_id=job.evaluation_id).update(
        {"prompt_text": None}
    )
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=1,
        justification="corrected",
    )

    pairs = list(export_dpo_pairs(db_session))
    assert pairs == []
    assert "no prompt_text snapshot" in caplog.text


def test_export_ignores_edit_for_unmatched_criterion_id(db_session, admin_user, caplog):
    caplog.set_level(logging.WARNING, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    # A real edit, so the evaluation still produces a pair...
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=2,
        justification="Reconsidered: partial evidence of concern.",
    )
    # ...and a stray edit referencing a criterion_id that was never
    # scored for this evaluation.
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-99",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="stray",
    )

    pairs = list(export_dpo_pairs(db_session))

    assert len(pairs) == 1
    chosen = json.loads(pairs[0].chosen)["criterion_scores"]
    assert "itso-99" not in chosen
    assert set(chosen) == {"itso-01", "itso-02", "itso-03"}
    assert "itso-99" in caplog.text
    assert "no matching CriterionScore row" in caplog.text


def test_main_reports_diversity_summary(
    db_session, admin_user, tmp_path, monkeypatch, caplog
):
    caplog.set_level(logging.INFO, logger="server.scripts.export_dpo_pairs")
    job = _seed_evaluation(db_session, user_id=admin_user.user_id)
    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-01",
        agent_name="itso",
        action="EDIT",
        user_id=admin_user.user_id,
        user_role="admin",
        score=3,
        justification="Adjusted for context.",
    )

    output_path = tmp_path / "export.jsonl"
    monkeypatch.setattr(
        "server.core.database.get_session_factory",
        lambda: (lambda: db_session),
    )
    monkeypatch.setattr(sys, "argv", ["export_dpo_pairs.py", str(output_path)])

    from server.scripts import export_dpo_pairs as module

    module.main()

    assert (
        "Wrote 1 DPO pairs across 1 evaluations, 1 documents, 1 reviewers"
        in caplog.text
    )
    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    written = json.loads(lines[0])
    assert set(written) == {"prompt", "chosen", "rejected"}
```

Also update `server/tests/scripts/conftest.py` to re-export `faculty_user`
too (needed by `test_export_tracks_multiple_reviewers_on_one_evaluation`):

```python
"""Re-export shared fixtures for scripts tests."""

from __future__ import annotations

from server.tests.admin.conftest import admin_user, faculty_user  # noqa: F401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/scripts -v`
Expected: FAIL — `export_dpo_pairs()` still returns dicts keyed by
`["prompt"]` etc. (`AttributeError: 'dict' object has no attribute
'prompt'`), and several new test scenarios (multi-criterion merging,
`main()`'s diversity log line) don't match current behavior at all.

- [ ] **Step 3: Rewrite the export script**

Replace the full contents of `server/scripts/export_dpo_pairs.py`:

```python
"""Export DPO training pairs from ITSO reviewer EDIT feedback.

Reads PreferenceLog EDIT rows for agent_name="itso", merges each with the
prompt snapshot and every criterion's original score/justification
captured on AgentResult / CriterionScore at scoring time, and yields one
DpoPair per evaluation:

    prompt: the exact prompt ITSO received (shared across all its criteria)
    chosen: the reviewer-corrected {criterion_id: {score, justification}}
        for every criterion -- corrected where a reviewer edited, the
        AI's original everywhere else
    rejected: the AI's original {criterion_id: {score, justification}}
        for every criterion

One pair per evaluation, not per criterion -- this matches what ITSO
actually generates: a single LLM call scoring every criterion together,
not one call per criterion. Pairing a corrected fragment against a
full-response prompt would be a category mismatch for DPO, which compares
complete responses to a prompt.

Every export run reads full history, not a delta since the last run --
re-running after more corrections come in is safe (each run is a fresh,
complete snapshot). Do NOT concatenate the output of two separate export
runs into one training session: the same evaluation could appear in both
at different points of completeness, producing overlapping/redundant
entries. Always train from a single, freshly generated export.

Rows/evaluations that can't produce a usable pair are logged and skipped,
never silently dropped.

Training itself is out of scope here -- this script only produces the
JSONL a separate, manually-run LoRA DPO training script consumes. See
docs/superpowers/specs/2026-08-10-dpo-itso-scoring-design.md and
docs/superpowers/specs/2026-08-11-itso-review-modal-and-export-design.md.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DpoPair:
    """One evaluation's DPO training pair: full-response chosen vs. rejected."""

    prompt: str
    chosen: str
    rejected: str
    evaluation_id: Any
    document_id: Any
    reviewer_ids: frozenset[Any]


def _is_real_change(
    edited_json: dict[str, Any] | None, original_score: CriterionScore
) -> bool:
    if not edited_json:
        return False
    edited_score = edited_json.get("score")
    edited_justification = str(edited_json.get("justification") or "").strip()
    original_justification = (original_score.justification or "").strip()
    return not (
        edited_score == original_score.score
        and edited_justification == original_justification
    )


def export_dpo_pairs(db: Any) -> Iterator[DpoPair]:
    """Yield one DpoPair per evaluation with at least one real ITSO correction."""

    edit_rows = (
        db.query(PreferenceLog)
        .filter(PreferenceLog.agent_name == "itso", PreferenceLog.action == "EDIT")
        .order_by(PreferenceLog.created_at.desc())
        .all()
    )

    latest_edit: dict[tuple[Any, str], PreferenceLog] = {}
    for log in edit_rows:
        grain = (log.evaluation_id, log.criterion_id)
        latest_edit.setdefault(grain, log)

    edits_by_evaluation: dict[Any, dict[str, PreferenceLog]] = defaultdict(dict)
    for (evaluation_id, criterion_id), log in latest_edit.items():
        edits_by_evaluation[evaluation_id][criterion_id] = log

    for evaluation_id, criterion_edits in edits_by_evaluation.items():
        agent_result = (
            db.query(AgentResult)
            .filter(
                AgentResult.evaluation_id == evaluation_id,
                AgentResult.agent_name == "itso",
            )
            .first()
        )
        if agent_result is None or not agent_result.prompt_text:
            logger.warning(
                "Skipping evaluation %s: no prompt_text snapshot (agent_result "
                "missing or predates prompt snapshotting). Affected preference "
                "logs: %s",
                evaluation_id,
                [str(log.log_id) for log in criterion_edits.values()],
            )
            continue

        original_scores = (
            db.query(CriterionScore)
            .filter(CriterionScore.agent_result_id == agent_result.agent_result_id)
            .all()
        )
        if not original_scores:
            logger.warning(
                "Skipping evaluation %s: no CriterionScore rows for its ITSO "
                "agent_result.",
                evaluation_id,
            )
            continue

        chosen_map: dict[str, dict[str, Any]] = {}
        rejected_map: dict[str, dict[str, Any]] = {}
        reviewer_ids: set[Any] = set()
        consumed_criterion_ids: set[str] = set()

        for score_row in original_scores:
            cid = score_row.criterion_id
            original_entry = {
                "score": score_row.score,
                "justification": score_row.justification,
            }
            rejected_map[cid] = original_entry

            log = criterion_edits.get(cid)
            if log is not None:
                consumed_criterion_ids.add(cid)

            if log is None or not _is_real_change(log.edited_json, score_row):
                if log is not None and not log.edited_json:
                    logger.warning(
                        "Preference log %s: EDIT action with empty edited_json "
                        "for criterion %s, falling back to the original value.",
                        log.log_id,
                        cid,
                    )
                elif log is not None:
                    logger.warning(
                        "Preference log %s: EDIT for criterion %s did not "
                        "change score or justification from the original, "
                        "falling back to the original value.",
                        log.log_id,
                        cid,
                    )
                chosen_map[cid] = original_entry
                continue

            chosen_map[cid] = {
                "score": log.edited_json.get("score"),
                "justification": log.edited_json.get("justification"),
            }
            reviewer_ids.add(log.user_id)

        unconsumed = set(criterion_edits) - consumed_criterion_ids
        for cid in unconsumed:
            logger.warning(
                "Preference log %s: criterion_id %s has no matching "
                "CriterionScore row for evaluation %s; ignored.",
                criterion_edits[cid].log_id,
                cid,
                evaluation_id,
            )

        if chosen_map == rejected_map:
            logger.warning(
                "Skipping evaluation %s: no criterion had a real correction "
                "survive (all edits degenerate, empty, or unmatched).",
                evaluation_id,
            )
            continue

        yield DpoPair(
            prompt=agent_result.prompt_text,
            chosen=json.dumps({"criterion_scores": chosen_map}, ensure_ascii=False),
            rejected=json.dumps(
                {"criterion_scores": rejected_map}, ensure_ascii=False
            ),
            evaluation_id=evaluation_id,
            document_id=agent_result.document_id,
            reviewer_ids=frozenset(reviewer_ids),
        )


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
        evaluations: set[Any] = set()
        documents: set[Any] = set()
        reviewers: set[Any] = set()
        with open(args.output, "w", encoding="utf-8") as f:
            for pair in export_dpo_pairs(session):
                f.write(
                    json.dumps(
                        {
                            "prompt": pair.prompt,
                            "chosen": pair.chosen,
                            "rejected": pair.rejected,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
                evaluations.add(pair.evaluation_id)
                documents.add(pair.document_id)
                reviewers.update(pair.reviewer_ids)
        logger.info(
            "Wrote %d DPO pairs across %d evaluations, %d documents, %d "
            "reviewers to %s",
            count,
            len(evaluations),
            len(documents),
            len(reviewers),
            args.output,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/scripts -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Lint**

Run: `uv run --project server ruff check server/scripts/export_dpo_pairs.py server/tests/scripts`
Expected: no new errors (pre-existing `E402` from the `sys.path.insert`
convention in the test file is expected and unrelated, per this
project's established pattern — confirm any reported errors are only
that pattern, nothing in the rewritten `export_dpo_pairs.py` itself).

- [ ] **Step 6: Commit**

```bash
git add server/scripts/export_dpo_pairs.py server/tests/scripts/test_export_dpo_pairs.py server/tests/scripts/conftest.py
git commit -m "feat(scripts): export one DPO pair per evaluation, not per criterion"
```

---

### Task 4: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `uv run --project server pytest`
Expected: PASS except the 8 known, pre-existing, unrelated Windows-platform
baseline failures documented in `docs/superpowers/plans/2026-08-10-dpo-itso-scoring.md`
(symlink privilege, chroma path normalization, directory fsync, open-file
deletion, one order-dependent embeddings flake). No failures outside that
list.

- [ ] **Step 2: Run the full backend lint**

Run: `uv run --project server ruff check server`
Expected: no new errors introduced by this plan's changed files (pre-existing
repo-wide debt is out of scope, per the prior phase's findings).

- [ ] **Step 3: Run the full frontend build**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors.

- [ ] **Step 4: Manually export a sample and eyeball it**

With at least one EDIT submitted via the new modal in Task 2's manual
test, run:
`uv run --project server python -m server.scripts.export_dpo_pairs /tmp/itso_dpo_pairs.jsonl`
and open the file. Confirm each line has a `"criterion_scores"` object
under both `chosen` and `rejected` covering all of that evaluation's
criteria, and that the log line reports the diversity summary
(`Wrote N DPO pairs across N evaluations, M documents, K reviewers`).
