import { Info } from 'lucide-react';

type EvaluationStatusBannerProps = {
  readonly status?: string;
};

export function EvaluationStatusBanner({
  status = 'Evaluation is advisory until reviewed and finalized by an authorized human reviewer.',
}: EvaluationStatusBannerProps) {
  return (
    <div className="flex items-start gap-3 rounded-sm border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning">
      <Info className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
      <p className="m-0 leading-6 text-text">{status}</p>
    </div>
  );
}
