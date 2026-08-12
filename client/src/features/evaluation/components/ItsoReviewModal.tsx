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

// Whether the draft currently differs from the true AI original -- used for
// the "edited" indicator (badge, blue button, header/footer counts). This is
// intentionally distinct from baselineFor(): a criterion with an existing
// prior correction has, by definition, already diverged from what the AI
// originally said, and should show as "edited" the moment the modal opens,
// independent of whether the reviewer touches anything further this
// session. baselineFor() answers a different question -- "should a new EDIT
// be submitted?" -- and must stay compared against the prior correction (or
// AI original if none) so reopening an already-corrected, untouched
// criterion sends zero requests on Save.
function isDifferentFromOriginal(criterion: CriterionScoreItem, draft: CriterionDraft): boolean {
  if (draft.rejected) return false;
  return (
    draft.score !== criterion.score ||
    draft.justification.trim() !== criterion.justification.trim()
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

  const editedCount = criteria.filter((criterion) =>
    isDifferentFromOriginal(criterion, drafts[criterion.criterion_id]),
  ).length;
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
            const isEdited = isDifferentFromOriginal(criterion, draft);
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
