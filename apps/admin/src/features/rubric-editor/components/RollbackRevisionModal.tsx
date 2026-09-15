import { ClockCounterClockwise, ShieldCheck, Spinner, X } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';
import { getRubricOperationError } from '../hooks/useRubrics';
import type { RubricSet } from '../types';

interface RollbackRevisionModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetRevision: RubricSet | null;
  agentLabel: string;
  onConfirmRollback: (rubricSetId: string) => Promise<void> | void;
  isPending: boolean;
  error?: unknown;
}

export function RollbackRevisionModal({
  isOpen,
  onClose,
  targetRevision,
  agentLabel,
  onConfirmRollback,
  isPending,
  error,
}: RollbackRevisionModalProps) {
  if (!isOpen || !targetRevision) return null;

  const criteriaCount = targetRevision.domains.reduce(
    (acc, d) => acc + (d.criteria?.length || 0),
    0,
  );

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await onConfirmRollback(targetRevision.rubric_set_id);
    } catch {
      // Error handled by parent/error prop
    }
  };

  const errorMessage = error ? getRubricOperationError(error) : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="rollback-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg rounded-md border border-border bg-surface shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-border p-4 sm:p-5 bg-surface-subtle">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-sm bg-primary/10 text-primary border border-primary/20 shrink-0">
              <ClockCounterClockwise className="size-4.5" aria-hidden="true" />
            </div>
            <div>
              <h2
                id="rollback-modal-title"
                className="text-sm sm:text-base font-bold text-text tracking-tight"
              >
                Rollback to Revision v{targetRevision.version_number}
              </h2>
              <p className="text-xs text-text-muted font-medium">Evaluator: {agentLabel}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="inline-flex size-8 items-center justify-center rounded-sm text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
            aria-label="Close rollback dialog"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleConfirm} className="p-5 sm:p-6 grid gap-4">
          {/* Institutional Compliance Notice */}
          <div className="flex items-start gap-3 rounded-sm border border-primary/20 bg-primary-soft/50 p-3.5 text-xs text-text">
            <ShieldCheck className="size-5 shrink-0 text-primary mt-0.5" aria-hidden="true" />
            <div className="space-y-1">
              <p className="font-bold text-text">Active Evaluation Pointer Rollback</p>
              <p className="text-text-muted leading-relaxed">
                Activating this published revision will immediately repoint the live multi-agent
                evaluation system for <strong>{agentLabel}</strong> to <strong>Revision v{targetRevision.version_number}</strong>.
              </p>
              <p className="text-[11px] text-text-muted/90 leading-relaxed">
                Existing evaluation records and previous scorecard histories will remain locked to
                their respective immutable snapshots and will not be altered.
              </p>
            </div>
          </div>

          {/* Target Revision Summary */}
          <div className="rounded-sm border border-border bg-surface-subtle/70 p-4 space-y-2 text-xs">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Target Revision Details
            </span>
            <div className="grid grid-cols-2 gap-2 text-xs pt-1">
              <div>
                <span className="text-text-muted font-medium">Form Name:</span>{' '}
                <span className="font-semibold text-text">{targetRevision.name}</span>
              </div>
              <div>
                <span className="text-text-muted font-medium">Version:</span>{' '}
                <span className="font-mono font-bold text-text">v{targetRevision.version_number}</span>
              </div>
              <div>
                <span className="text-text-muted font-medium">Domains:</span>{' '}
                <span className="font-semibold text-text tabular-nums">{targetRevision.domains.length}</span>
              </div>
              <div>
                <span className="text-text-muted font-medium">Criteria:</span>{' '}
                <span className="font-semibold text-text tabular-nums">{criteriaCount} criteria</span>
              </div>
            </div>
            {targetRevision.published_at && (
              <p className="text-[11px] text-text-muted pt-1 border-t border-border/60">
                Originally published on{' '}
                <span className="font-semibold text-text">
                  {new Date(targetRevision.published_at).toLocaleDateString()}
                </span>
              </p>
            )}
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div
              role="alert"
              className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive"
            >
              {errorMessage}
            </div>
          )}

          {/* Modal Action Buttons */}
          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={onClose}
              disabled={isPending}
              className="text-xs h-9 px-4 font-semibold"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={isPending}
              isLoading={isPending}
              className="text-xs h-9 px-4 font-semibold"
            >
              {isPending ? (
                <>
                  <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                  <span>Rolling back…</span>
                </>
              ) : (
                <span>Confirm Rollback to v{targetRevision.version_number}</span>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
