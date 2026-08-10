import { useState } from 'react';
import { Check, X, Pencil } from 'lucide-react';
import { useSubmitCriterionFeedback } from '../hooks/useSubmitFeedback';
import type { CriterionScoreItem } from '../types';

type CriterionFeedbackControlsProps = {
  readonly evaluationId: string;
  readonly criterion: CriterionScoreItem;
};

export function CriterionFeedbackControls({
  evaluationId,
  criterion,
}: CriterionFeedbackControlsProps) {
  const [mode, setMode] = useState<'idle' | 'editing'>('idle');
  const [score, setScore] = useState(criterion.score);
  const [justification, setJustification] = useState(criterion.justification);
  const [submittedAction, setSubmittedAction] = useState<
    'ACCEPT' | 'REJECT' | 'EDIT' | null
  >(null);
  const mutation = useSubmitCriterionFeedback(evaluationId);

  function submit(
    action: 'ACCEPT' | 'REJECT' | 'EDIT',
    body: { score?: number; justification?: string } = {},
  ) {
    mutation.mutate(
      {
        criterionId: criterion.criterion_id,
        body: { agent_name: 'itso', action, ...body },
      },
      { onSuccess: () => setSubmittedAction(action) },
    );
    setMode('idle');
  }

  if (submittedAction) {
    return (
      <span className="inline-flex items-center rounded-sm border border-slate-200 bg-slate-50 px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-slate-500">
        {submittedAction === 'ACCEPT'
          ? 'Accepted'
          : submittedAction === 'REJECT'
            ? 'Rejected'
            : 'Edited'}
      </span>
    );
  }

  if (mode === 'editing') {
    return (
      <div className="grid gap-2 rounded-sm border border-slate-200 bg-white p-2">
        <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Corrected score
          <select
            className="mt-1 block w-full rounded-sm border border-slate-200 px-2 py-1 text-xs"
            value={score}
            onChange={(event) => setScore(Number(event.target.value))}
          >
            {[1, 2, 3, 4].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Corrected justification
          <textarea
            className="mt-1 block w-full rounded-sm border border-slate-200 px-2 py-1 text-xs"
            rows={3}
            value={justification}
            onChange={(event) => setJustification(event.target.value)}
          />
        </label>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[#1b3b87]"
            onClick={() => submit('EDIT', { score, justification })}
            disabled={!justification.trim()}
          >
            Save correction
          </button>
          <button
            type="button"
            className="rounded-sm border border-slate-200 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-500"
            onClick={() => setMode('idle')}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-1.5">
      <button
        type="button"
        title="Accept"
        className="inline-flex size-6 items-center justify-center rounded-sm border border-[#3b963e]/30 text-[#3b963e] hover:bg-[#3b963e]/10"
        onClick={() => submit('ACCEPT')}
        disabled={mutation.isPending}
      >
        <Check className="size-3.5" />
      </button>
      <button
        type="button"
        title="Reject"
        className="inline-flex size-6 items-center justify-center rounded-sm border border-[#b91c1c]/30 text-[#b91c1c] hover:bg-[#b91c1c]/10"
        onClick={() => submit('REJECT')}
        disabled={mutation.isPending}
      >
        <X className="size-3.5" />
      </button>
      <button
        type="button"
        title="Edit"
        className="inline-flex size-6 items-center justify-center rounded-sm border border-slate-300 text-slate-500 hover:bg-slate-50"
        onClick={() => setMode('editing')}
        disabled={mutation.isPending}
      >
        <Pencil className="size-3.5" />
      </button>
    </div>
  );
}
