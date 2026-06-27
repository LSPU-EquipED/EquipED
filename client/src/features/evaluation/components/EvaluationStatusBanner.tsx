import { Info } from 'lucide-react';

type EvaluationStatusBannerProps = {
  readonly status?: string;
};

export function EvaluationStatusBanner({
  status = 'Evaluation is advisory until reviewed and finalized by an authorized human reviewer.',
}: EvaluationStatusBannerProps) {
  return (
    <div className="flex items-start gap-3 rounded-sm border border-[#f2c811]/30 bg-[#f2c811]/10 px-4 py-3 text-sm text-[#1e293b]">
      <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p className="m-0 leading-6">{status}</p>
    </div>
  );
}
