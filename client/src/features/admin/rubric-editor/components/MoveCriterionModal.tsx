import { useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { getRubricOperationError } from '../hooks/useRubrics';
import type { RubricCriterion, RubricDomain } from '../types';

interface MoveCriterionModalProps {
  isOpen: boolean;
  onClose: () => void;
  criterion: RubricCriterion | null;
  currentDomainId: string;
  availableDomains: RubricDomain[];
  onMove: (destinationDomainId: string) => Promise<void> | void;
  isPending: boolean;
  error?: unknown;
}

function MoveCriterionModalContent({
  onClose,
  criterion,
  currentDomainId,
  availableDomains,
  onMove,
  isPending,
  error,
}: Omit<MoveCriterionModalProps, 'isOpen'>) {
  const otherDomains = availableDomains.filter((d) => d.rubric_domain_id !== currentDomainId);

  const [destinationDomainId, setDestinationDomainId] = useState<string>(
    otherDomains[0]?.rubric_domain_id ?? '',
  );

  if (!criterion) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!destinationDomainId) return;
    try {
      await onMove(destinationDomainId);
    } catch {
      // Handled by parent
    }
  };

  const errorMessage = error ? getRubricOperationError(error) : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="move-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-md rounded-sm border border-slate-200 bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 p-4 bg-slate-50">
          <div>
            <h2
              id="move-modal-title"
              className="text-sm font-bold uppercase tracking-wider text-slate-800"
            >
              Move Criterion
            </h2>
            <p className="text-xs text-slate-500 font-medium">
              Criterion: <strong className="text-slate-700">{criterion.criterion_code}</strong>
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="inline-flex size-8 items-center justify-center rounded-sm text-slate-400 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
            aria-label="Close move criterion dialog"
          >
            <X className="size-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 grid gap-4">
          {errorMessage && (
            <div
              role="alert"
              className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-xs font-semibold text-[#b91c1c]"
            >
              {errorMessage}
            </div>
          )}

          {otherDomains.length === 0 ? (
            <p className="text-xs text-slate-600 font-medium">
              There are no other domains available to move this criterion into. Create another
              domain first.
            </p>
          ) : (
            <div>
              <label
                htmlFor="destination-domain-select"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Destination Domain <span className="text-[#b91c1c]">*</span>
              </label>
              <select
                id="destination-domain-select"
                value={destinationDomainId}
                onChange={(e) => setDestinationDomainId(e.target.value)}
                disabled={isPending}
                className="mt-1.5 w-full h-9 rounded-sm border border-slate-300 bg-white px-2.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              >
                {otherDomains.map((d) => (
                  <option key={d.rubric_domain_id} value={d.rubric_domain_id}>
                    {d.code} — {d.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 border-t border-slate-200 pt-4 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="h-9 px-3 rounded-sm border border-slate-300 bg-white text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || otherDomains.length === 0 || !destinationDomainId}
              className="inline-flex h-9 items-center justify-center gap-1.5 px-4 rounded-sm bg-[#1b3b87] text-xs font-bold uppercase tracking-wider text-white hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50"
            >
              {isPending && <Loader2 className="size-3.5 animate-spin" />}
              Move Criterion
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function MoveCriterionModal(props: MoveCriterionModalProps) {
  if (!props.isOpen) return null;

  return (
    <MoveCriterionModalContent
      key={`${props.currentDomainId}-${props.criterion?.rubric_criterion_id || 'new'}`}
      {...props}
    />
  );
}
