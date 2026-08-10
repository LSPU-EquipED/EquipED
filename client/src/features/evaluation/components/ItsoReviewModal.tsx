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
