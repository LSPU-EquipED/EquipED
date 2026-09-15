import { useState } from 'react';
import { Spinner, X } from '@phosphor-icons/react';
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-md rounded-sm border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border p-4 bg-surface-subtle">
          <div>
            <h2
              id="move-modal-title"
              className="text-sm font-bold uppercase tracking-wider text-text"
            >
              Move Criterion
            </h2>
            <p className="text-xs text-text-muted font-medium">
              Criterion: <strong className="text-text">{criterion.criterion_code}</strong>
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="inline-flex size-8 items-center justify-center rounded-sm text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close move criterion dialog"
          >
            <X className="size-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 grid gap-4">
          {errorMessage && (
            <div
              role="alert"
              className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive"
            >
              {errorMessage}
            </div>
          )}

          {otherDomains.length === 0 ? (
            <p className="text-xs text-text-muted font-medium">
              There are no other domains available to move this criterion into. Create another
              domain first.
            </p>
          ) : (
            <div>
              <label
                htmlFor="destination-domain-select"
                className="block text-xs font-bold uppercase tracking-wider text-text"
              >
                Destination Domain <span className="text-destructive">*</span>
              </label>
              <select
                id="destination-domain-select"
                value={destinationDomainId}
                onChange={(e) => setDestinationDomainId(e.target.value)}
                disabled={isPending}
                className="mt-1.5 w-full h-9 rounded-sm border border-input bg-surface px-2.5 text-xs font-bold text-text focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {otherDomains.map((d) => (
                  <option key={d.rubric_domain_id} value={d.rubric_domain_id}>
                    {d.code} — {d.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 border-t border-border pt-4 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="h-9 px-3 rounded-sm border border-border bg-surface text-xs font-bold uppercase tracking-wider text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || otherDomains.length === 0 || !destinationDomainId}
              className="inline-flex h-9 items-center justify-center gap-1.5 px-4 rounded-sm bg-primary text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              {isPending && <Spinner className="size-3.5 animate-spin" />}
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
