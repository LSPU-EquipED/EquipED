import { MessageSquareText, Quote } from 'lucide-react';
import type { CriterionScoreItem } from '../types';
import { cleanJustification } from '../utils/scoreHelpers';

type FeedbackPanelProps = {
  readonly criteria?: readonly CriterionScoreItem[];
};

export function FeedbackPanel({ criteria = [] }: FeedbackPanelProps) {
  const hasFeedback = criteria.length > 0;

  return (
    <div className="grid gap-2">
      {hasFeedback ? (
        criteria.map((item) => (
          <div
            key={item.criterion_id}
            className="flex gap-3 rounded-lg border bg-white p-3 text-sm transition duration-200 hover:bg-slate-50/30"
          >
            <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-slate-50 text-slate-500">
              <MessageSquareText className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium leading-snug text-slate-900">{item.criterion_text}</p>
              {item.justification && (
                <p className="mt-1.5 leading-relaxed text-slate-500">
                  {cleanJustification(item.justification)}
                </p>
              )}
              {item.evidence && (
                <div className="mt-2 flex items-start gap-1.5 rounded-md border bg-slate-50/30 px-2.5 py-1.5">
                  <Quote className="mt-0.5 size-3 shrink-0 text-slate-500" aria-hidden="true" />
                  <p className="text-xs leading-relaxed text-slate-500">{item.evidence}</p>
                </div>
              )}
            </div>
          </div>
        ))
      ) : (
        <div className="flex gap-3 rounded-lg border bg-white p-3 text-sm">
          <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-slate-50 text-slate-500">
            <MessageSquareText className="size-4" aria-hidden="true" />
          </span>
          <p className="m-0 leading-6 text-slate-500">
            Agent feedback will appear here after persisted Layer 3 outputs are available for this
            job.
          </p>
        </div>
      )}
    </div>
  );
}
