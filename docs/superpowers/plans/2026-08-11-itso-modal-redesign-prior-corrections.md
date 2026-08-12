# ITSO Modal Redesign + Prior-Correction Awareness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface a reviewer's own prior correction when the ITSO review modal reopens (instead of always showing the AI's original with no trace of past feedback), redesign the modal's visuals to be compact-by-default with per-criterion expand/collapse, and fix the header button's clipping.

**Architecture:** Backend: `get_evaluation_results` gains a read-only `reviewer_correction` field per ITSO criterion, sourced from the latest `PreferenceLog` row (additive, every other consumer of that response is unaffected). Frontend: the modal computes each criterion's "baseline" (prior correction if one exists, else the AI original) once from that data and uses it — not the raw AI original — for all "did this change" comparisons and for what's pre-filled/pre-expanded on open.

**Tech Stack:** Python 3.12 + SQLAlchemy + Pydantic (backend), React 18 + TypeScript + Tailwind (frontend), same stack as the rest of this feature.

## Global Constraints

- Backend: ruff-enforced (E, F, I, UP), line length 88, Python 3.12. Run backend commands from the repo root with `--project server`, never from inside `server/`.
- Frontend: TypeScript, ESLint (react-hooks, react-refresh) + Prettier. No shadcn/ui or external component kits — Tailwind utility classes only, matching this feature's existing style.
- No change to the main Scorecard table's displayed score/subtotal/adjectival rating — those stay computed from the AI's original output only. This plan is scoped to the review modal and its header button.
- No new backend endpoint, no `PreferenceLog`/database schema changes.
- No new frontend component-test infrastructure — verify via `pnpm lint` + `pnpm build` + a manual browser walkthrough, consistent with this feature area's established convention.

---

### Task 1: Surface `reviewer_correction` on `get_evaluation_results`

**Files:**
- Modify: `server/modules/synthesis/schemas.py`
- Modify: `server/modules/synthesis/service.py`
- Test: `server/tests/synthesis/test_service.py` (new)

**Interfaces:**
- Consumes: `PreferenceLog` (existing, `server/modules/feedback/models.py`) — `agent_name`, `criterion_id`, `action`, `edited_json`, `created_at`.
- Produces: `CriterionScoreItem.reviewer_correction: ReviewerCorrection | None` — Task 2's frontend type and modal both consume this exact shape (`{action: "EDIT"|"REJECT", score: int|None, justification: str|None}`, or `null`).

- [ ] **Step 1: Write the failing tests**

Create `server/tests/synthesis/test_service.py`:

```python
"""Tests for get_evaluation_results' reviewer_correction surfacing."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.modules.synthesis.service import get_evaluation_results


def _seed(db_session, *, user_id):
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
    job = EvaluationJob(
        evaluation_id=uuid4(), document_id=document_id, submitted_by=user_id
    )
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name="itso",
        subtotal=2.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="ok",
        success=True,
        prompt_text='{"agent": "itso"}',
    )
    db_session.add(agent_result)
    db_session.flush()

    for criterion_id, score, justification in [
        ("itso-01", 4, "No plagiarism detected."),
        ("itso-02", 1, "No reference section found."),
        ("itso-03", 2, "No ownership statement present."),
    ]:
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


def test_untouched_criterion_has_no_reviewer_correction(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    assert by_id["itso-01"].reviewer_correction is None


def test_edited_criterion_surfaces_latest_correction(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={"score": 3, "justification": "Reference section is included"},
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    correction = by_id["itso-02"].reviewer_correction
    assert correction is not None
    assert correction.action == "EDIT"
    assert correction.score == 3
    assert correction.justification == "Reference section is included"


def test_rejected_criterion_has_no_score_or_justification(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-03",
            action="REJECT",
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    correction = by_id["itso-03"].reviewer_correction
    assert correction is not None
    assert correction.action == "REJECT"
    assert correction.score is None
    assert correction.justification is None


def test_only_latest_edit_wins(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={"score": 2, "justification": "first correction"},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-02",
            action="EDIT",
            edited_json={
                "score": 3,
                "justification": "second, more recent correction",
            },
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    correction = by_id["itso-02"].reviewer_correction
    assert correction.score == 3
    assert correction.justification == "second, more recent correction"


def test_accept_action_does_not_surface_as_reviewer_correction(db_session, seeded_user):
    job = _seed(db_session, user_id=seeded_user.user_id)
    db_session.add(
        PreferenceLog(
            evaluation_id=job.evaluation_id,
            user_id=seeded_user.user_id,
            agent_name="itso",
            criterion_id="itso-01",
            action="ACCEPT",
        )
    )
    db_session.commit()

    result = get_evaluation_results(job.evaluation_id, seeded_user.user_id, db_session)

    by_id = {c.criterion_id: c for c in result.domain_scores["itso"].criteria}
    assert by_id["itso-01"].reviewer_correction is None
```

Note: this test file relies on the root `seeded_user` fixture (`server/tests/conftest.py`, an admin-role user already available globally — no re-export needed) and the global `db_session` fixture.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --project server pytest server/tests/synthesis/test_service.py -v`
Expected: FAIL — `AttributeError: 'CriterionScoreItem' object has no attribute 'reviewer_correction'`

- [ ] **Step 3: Add the `ReviewerCorrection` schema and field**

In `server/modules/synthesis/schemas.py`, add `Literal` to the imports and a new schema, then extend `CriterionScoreItem`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewerCorrection(BaseModel):
    action: Literal["EDIT", "REJECT"]
    score: int | None = None
    justification: str | None = None


class CriterionScoreItem(BaseModel):
    criterion_id: str
    criterion_text: str
    score: int
    justification: str
    evidence: str | None = None
    chunk_ids: str | None = None
    reviewer_correction: ReviewerCorrection | None = None
```

- [ ] **Step 4: Populate it in `get_evaluation_results`**

In `server/modules/synthesis/service.py`, add the import (alongside the existing `from server.modules.evaluations.models import EvaluationJob` line):

```python
from server.modules.feedback.models import PreferenceLog
```

Add a helper function above `get_evaluation_results` (after the imports, before the function definitions already in the file):

```python
def _reviewer_correction_payload(log: PreferenceLog | None) -> dict[str, Any] | None:
    if log is None:
        return None
    edited = log.edited_json or {}
    return {
        "action": log.action,
        "score": edited.get("score"),
        "justification": edited.get("justification"),
    }
```

Inside `get_evaluation_results` (currently lines 136-197), after the existing `flags = db.query(EvaluationFlag)...` line and before `synthesis_result = compute_synthesized_score(...)`, add the correction lookup:

```python
    # Latest ITSO reviewer correction per criterion (latest wins, same rule
    # export_dpo_pairs.py already uses). ACCEPT is excluded -- it carries
    # no score/justification and nothing in the UI sends it anymore.
    itso_corrections: dict[str, PreferenceLog] = {}
    for log in (
        db.query(PreferenceLog)
        .filter(
            PreferenceLog.evaluation_id == evaluation_id,
            PreferenceLog.agent_name == "itso",
            PreferenceLog.action.in_(["EDIT", "REJECT"]),
        )
        .order_by(PreferenceLog.created_at.desc())
        .all()
    ):
        itso_corrections.setdefault(log.criterion_id, log)
```

Then modify the `domain_scores` dict comprehension's inner `"criteria"` list (currently lines 176-186) to add the new field:

```python
            "criteria": [
                {
                    "criterion_id": score.criterion_id,
                    "criterion_text": score.criterion_title,
                    "score": score.score,
                    "justification": score.justification,
                    "evidence": score.evidence,
                    "chunk_ids": score.chunk_ids,
                    "reviewer_correction": (
                        _reviewer_correction_payload(
                            itso_corrections.get(score.criterion_id)
                        )
                        if result.agent_name == "itso"
                        else None
                    ),
                }
                for score in criteria_by_result.get(result.agent_result_id, [])
            ],
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --project server pytest server/tests/synthesis/test_service.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 6: Run the full synthesis suite to check nothing else broke**

Run: `uv run --project server pytest server/tests/synthesis -v`
Expected: PASS

- [ ] **Step 7: Lint**

Run: `uv run --project server ruff check server/modules/synthesis server/tests/synthesis/test_service.py`
Expected: no new errors

- [ ] **Step 8: Commit**

```bash
git add server/modules/synthesis/schemas.py server/modules/synthesis/service.py server/tests/synthesis/test_service.py
git commit -m "feat(synthesis): surface latest ITSO reviewer correction per criterion"
```

---

### Task 2: Redesigned `ItsoReviewModal` with baseline-aware data

**Files:**
- Modify: `client/src/features/evaluation/types.ts`
- Modify: `client/src/features/evaluation/components/ItsoReviewModal.tsx`

**Interfaces:**
- Consumes: `CriterionScoreItem.reviewer_correction` from Task 1 (exact shape:
  `{action: 'EDIT' | 'REJECT', score: number | null, justification: string | null} | null`).
  `useSubmitCriterionFeedback` (existing, unchanged). `formatScore` (existing,
  `client/src/features/evaluation/utils/scoreHelpers.ts`).
- Produces: `ItsoReviewModal({evaluationId, criteria, onClose})` — same
  external props as before; Task 3 (Scorecard wiring) is unaffected and
  needs no changes for this task.

- [ ] **Step 1: Add the `reviewer_correction` field to the frontend type**

In `client/src/features/evaluation/types.ts`, modify `CriterionScoreItem`:

```typescript
export type CriterionReviewerCorrection = {
  action: 'EDIT' | 'REJECT';
  score: number | null;
  justification: string | null;
};

export interface CriterionScoreItem {
  criterion_id: string;
  criterion_text: string;
  score: number;
  justification: string;
  evidence?: string | null;
  chunk_ids?: string | null;
  reviewer_correction?: CriterionReviewerCorrection | null;
}
```

- [ ] **Step 2: Replace the full contents of `ItsoReviewModal.tsx`**

```tsx
import { useState } from 'react';
import { Flag, X } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import { useSubmitCriterionFeedback } from '../hooks/useSubmitFeedback';
import { formatScore } from '../utils/scoreHelpers';
import type { CriterionScoreItem } from '../types';

type CriterionDraft = {
  score: number;
  justification: string;
  rejected: boolean;
  expanded: boolean;
};

type ItsoReviewModalProps = {
  readonly evaluationId: string;
  readonly criteria: readonly CriterionScoreItem[];
  readonly onClose: () => void;
};

function baselineFor(
  criterion: CriterionScoreItem,
): { score: number; justification: string } {
  if (criterion.reviewer_correction?.action === 'EDIT') {
    return {
      score: criterion.reviewer_correction.score ?? criterion.score,
      justification: criterion.reviewer_correction.justification ?? criterion.justification,
    };
  }
  return { score: criterion.score, justification: criterion.justification };
}

function initialDrafts(
  criteria: readonly CriterionScoreItem[],
): Record<string, CriterionDraft> {
  return Object.fromEntries(
    criteria.map((c) => {
      const baseline = baselineFor(c);
      const isEditBaseline = c.reviewer_correction?.action === 'EDIT';
      return [
        c.criterion_id,
        {
          score: baseline.score,
          justification: baseline.justification,
          rejected: c.reviewer_correction?.action === 'REJECT',
          expanded: isEditBaseline,
        },
      ];
    }),
  );
}

function scoreButtonClasses(value: number, selected: boolean, isEdited: boolean): string {
  if (!selected) {
    return 'border-slate-200 text-slate-400 hover:bg-slate-50';
  }
  if (isEdited) {
    return 'border-[#1b3b87] bg-[#1b3b87] text-white';
  }
  return value < 2
    ? 'border-[#b91c1c] bg-[#b91c1c] text-white'
    : 'border-[#3b963e] bg-[#3b963e] text-white';
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

  function selectScore(criterion: CriterionScoreItem, value: number) {
    updateDraft(criterion.criterion_id, { score: value, expanded: true });
  }

  function toggleRejected(criterion: CriterionScoreItem) {
    const draft = drafts[criterion.criterion_id];
    const nextRejected = !draft.rejected;
    updateDraft(criterion.criterion_id, {
      rejected: nextRejected,
      expanded: nextRejected ? false : draft.expanded,
    });
  }

  function revertCriterion(criterion: CriterionScoreItem) {
    updateDraft(criterion.criterion_id, {
      score: criterion.score,
      justification: criterion.justification,
      rejected: false,
      expanded: false,
    });
  }

  // A criterion that isn't flagged as incorrect must keep a non-empty
  // justification -- an empty EDIT justification is rejected by the backend
  // (422) and, if it ever slipped through as whitespace, would pollute DPO
  // training data. Block submission per-criterion instead of surfacing a
  // generic post-submit failure.
  const emptyJustificationIds = criteria
    .filter((criterion) => {
      const draft = drafts[criterion.criterion_id];
      return !draft.rejected && draft.justification.trim() === '';
    })
    .map((criterion) => criterion.criterion_id);
  const hasEmptyJustification = emptyJustificationIds.length > 0;

  const editedCount = criteria.filter((criterion) => {
    const draft = drafts[criterion.criterion_id];
    if (draft.rejected) return false;
    const baseline = baselineFor(criterion);
    return (
      draft.score !== baseline.score ||
      draft.justification.trim() !== baseline.justification.trim()
    );
  }).length;
  const flaggedCount = criteria.filter(
    (criterion) => drafts[criterion.criterion_id].rejected,
  ).length;
  const draftSubtotal = criteria.length
    ? criteria.reduce((sum, criterion) => sum + drafts[criterion.criterion_id].score, 0) /
      criteria.length
    : 0;

  async function handleSubmit() {
    setSubmitError(null);

    if (hasEmptyJustification) {
      setSubmitError('Justification cannot be empty. Fix the highlighted criteria below.');
      return;
    }

    const actions = criteria
      .map((criterion) => {
        const draft = drafts[criterion.criterion_id];
        const wasRejected = criterion.reviewer_correction?.action === 'REJECT';

        if (draft.rejected) {
          // Only send REJECT if this is a new rejection this session --
          // reopening an already-rejected, untouched criterion and
          // resubmitting must send zero requests, same as any other
          // unchanged criterion.
          if (wasRejected) return null;
          return {
            criterionId: criterion.criterion_id,
            body: { agent_name: 'itso' as const, action: 'REJECT' as const },
          };
        }

        const baseline = baselineFor(criterion);
        const trimmedJustification = draft.justification.trim();
        const scoreChanged = draft.score !== baseline.score;
        const justificationChanged = trimmedJustification !== baseline.justification.trim();
        if (scoreChanged || justificationChanged) {
          return {
            criterionId: criterion.criterion_id,
            body: {
              agent_name: 'itso' as const,
              action: 'EDIT' as const,
              score: draft.score,
              justification: trimmedJustification,
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
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
              Review ITSO Scores
            </h2>
            <p className="mt-0.5 text-[11px] text-slate-500">
              {editedCount} of {criteria.length} edited · subtotal{' '}
              {formatScore(draftSubtotal)}/4
            </p>
          </div>
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

        <div className="grid gap-3 px-5 py-4">
          {criteria.map((criterion) => {
            const draft = drafts[criterion.criterion_id];
            const baseline = baselineFor(criterion);
            const isEdited =
              !draft.rejected &&
              (draft.score !== baseline.score ||
                draft.justification.trim() !== baseline.justification.trim());
            const isJustificationEmpty = emptyJustificationIds.includes(
              criterion.criterion_id,
            );

            return (
              <div
                key={criterion.criterion_id}
                className="grid gap-2 rounded-sm border border-slate-200 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-800">
                      {criterion.criterion_text}
                    </span>
                    {isEdited && (
                      <span className="rounded-full bg-[#1b3b87]/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[#1b3b87]">
                        Edited
                      </span>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {[1, 2, 3, 4].map((value) => (
                      <button
                        key={value}
                        type="button"
                        disabled={draft.rejected}
                        onClick={() => selectScore(criterion, value)}
                        className={cn(
                          'inline-flex size-6 items-center justify-center rounded-sm border text-xs font-bold disabled:cursor-not-allowed disabled:opacity-40',
                          scoreButtonClasses(value, draft.score === value, isEdited),
                        )}
                      >
                        {value}
                      </button>
                    ))}
                    <button
                      type="button"
                      title="Flag as incorrect"
                      onClick={() => toggleRejected(criterion)}
                      className={cn(
                        'inline-flex size-6 shrink-0 items-center justify-center rounded-sm border',
                        draft.rejected
                          ? 'border-[#b91c1c] bg-[#b91c1c]/10 text-[#b91c1c]'
                          : 'border-slate-200 text-slate-400 hover:bg-slate-50',
                      )}
                    >
                      <Flag className="size-3.5" />
                    </button>
                  </div>
                </div>

                {!draft.expanded && (
                  <p className="text-xs leading-relaxed text-slate-500">
                    {criterion.justification}
                  </p>
                )}

                {draft.expanded && !draft.rejected && (
                  <div className="grid gap-1">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      Justification
                      <textarea
                        className={cn(
                          'mt-1 block w-full rounded-sm border px-2 py-1 text-xs',
                          isJustificationEmpty
                            ? 'border-[#b91c1c] focus:outline-[#b91c1c]'
                            : 'border-slate-200',
                        )}
                        rows={2}
                        maxLength={4000}
                        value={draft.justification}
                        onChange={(event) =>
                          updateDraft(criterion.criterion_id, {
                            justification: event.target.value,
                          })
                        }
                      />
                      {isJustificationEmpty && (
                        <span className="mt-1 block text-[10px] font-normal normal-case tracking-normal text-[#b91c1c]">
                          Justification cannot be empty.
                        </span>
                      )}
                    </label>
                    <p className="text-[11px] text-slate-400">
                      AI scored {formatScore(criterion.score)}/4 — {criterion.justification}.{' '}
                      <button
                        type="button"
                        className="font-semibold text-[#1b3b87] hover:underline"
                        onClick={() => revertCriterion(criterion)}
                      >
                        Revert
                      </button>
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-slate-200 px-5 py-4">
          <p className="text-[11px] text-slate-500">
            {submitError ? (
              <span className="font-semibold text-[#b91c1c]">{submitError}</span>
            ) : (
              `${flaggedCount} flagged · ${editedCount} edited`
            )}
          </p>
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
              disabled={isSubmitting || hasEmptyJustification}
            >
              {isSubmitting ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Lint and typecheck**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors

- [ ] **Step 4: Manual verification in the browser**

Run: `cd client && pnpm dev`, navigate to a completed evaluation's Scorecard. Using an evaluation where you've previously submitted an EDIT (from earlier manual testing), confirm:
- Opening "Review Scores" pre-expands the previously-edited criterion, showing **your correction** (not the AI's original) in the score/justification fields, with an "Edited" badge and the "AI scored X/4 — ... Revert" hint line underneath.
- The header subtitle (`"N of 5 edited · subtotal X.XX/4"`) counts that prior correction from the moment the modal opens, before touching anything.
- Clicking Save changes immediately (no new edits) sends **zero** requests for that already-corrected criterion (Network tab) — confirms the baseline comparison, not the raw AI original, is what's being checked.
- Clicking a score button (1-4) on a still-compact, untouched criterion expands it into the editable state.
- Clicking "Revert" on the previously-edited criterion resets it to the true AI original (not just collapses it) and collapses it back to compact display.
- Flagging a criterion "incorrect" (the flag icon) disables its score buttons and collapses/hides any expanded justification field; the flag icon shows a red border while active.
- The edited score's selected button renders blue; an unedited, untouched criterion's selected button renders red (score 1) or green (score 2-4), matching the rest of the app's color convention.

- [ ] **Step 5: Commit**

```bash
git add client/src/features/evaluation/types.ts client/src/features/evaluation/components/ItsoReviewModal.tsx
git commit -m "feat(evaluation): redesign ITSO review modal, show prior corrections"
```

---

### Task 3: Fix the "Review Scores" header button placement

**Files:**
- Modify: `client/src/features/evaluation/components/Scorecard.tsx`

**Interfaces:**
- Consumes: nothing new — this task only moves existing JSX within `Scorecard.tsx`. Independent of Tasks 1-2; can be done before, after, or interleaved with them.

- [ ] **Step 1: Move the button into the domain-label cell**

In `client/src/features/evaluation/components/Scorecard.tsx`, find the "Domain Group Header Row" block (currently around lines 342-372):

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

Replace it with (button moves to the first `<td>`, next to the domain label; the Status cell reverts to just the badge):

```tsx
                        <tr className="bg-slate-50/60 select-none">
                          <td className="py-3 px-4 text-[10px] font-extrabold text-slate-800 uppercase tracking-widest border-t border-slate-200">
                            <div className="flex items-center gap-3">
                              <span>{agentLabels[domain]}</span>
                              {domain === 'itso' && (
                                <button
                                  type="button"
                                  className="shrink-0 rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-2 py-1 text-[9px] font-bold normal-case tracking-wide text-[#1b3b87] hover:bg-[#1b3b87]/10"
                                  onClick={() => setIsItsoReviewOpen(true)}
                                >
                                  Review Scores
                                </button>
                              )}
                            </div>
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
                        </tr>
```

(Note: `normal-case` on the button is needed because the parent `<td>` sets `uppercase` for the domain label — without it, "Review Scores" would render as "REVIEW SCORES" via inherited text-transform. `tracking-wide` is kept for the button's own letter-spacing intent, but reset from the parent's `tracking-widest`.)

- [ ] **Step 2: Lint and typecheck**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors

- [ ] **Step 3: Manual verification**

In the browser, confirm the "Review Scores" button now renders fully next to "INNOVATION AND IP (ITSO)" with no clipping, in normal sentence-style casing (not uppercase like the domain label), and that SME/Coordinator/GAD rows are visually unchanged (label only, no button).

- [ ] **Step 4: Commit**

```bash
git add client/src/features/evaluation/components/Scorecard.tsx
git commit -m "fix(evaluation): move Review Scores button to the domain-label cell"
```

---

### Task 4: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `uv run --project server pytest`
Expected: PASS except the 8 known, pre-existing, unrelated Windows-platform
baseline failures documented in `docs/superpowers/plans/2026-08-10-dpo-itso-scoring.md`.

- [ ] **Step 2: Run the full backend lint**

Run: `uv run --project server ruff check server`
Expected: no new errors introduced by this plan's changed files.

- [ ] **Step 3: Run the full frontend build**

Run: `cd client && pnpm lint && pnpm build`
Expected: no errors.

- [ ] **Step 4: End-to-end manual walkthrough**

With the app running, on one evaluation: submit a fresh EDIT via the redesigned modal, reopen it and confirm the correction is shown pre-filled/pre-expanded, submit with no further changes and confirm zero network requests fire, then use Revert on that same criterion and confirm it returns to the true AI original.
