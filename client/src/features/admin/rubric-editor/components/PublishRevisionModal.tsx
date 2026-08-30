import { useState } from 'react';
import { AlertTriangle, Loader2, X } from 'lucide-react';
import { getRubricOperationError, getValidationReportFromError } from '../hooks/useRubrics';
import { ValidationReportCard } from './ValidationReportCard';

interface PublishRevisionModalProps {
  isOpen: boolean;
  onClose: () => void;
  versionNumber: number;
  agentLabel: string;
  onPublish: (activate: boolean) => Promise<void> | void;
  isPending: boolean;
  error?: unknown;
}

export function PublishRevisionModal({
  isOpen,
  onClose,
  versionNumber,
  agentLabel,
  onPublish,
  isPending,
  error,
}: PublishRevisionModalProps) {
  const [activate, setActivate] = useState<boolean>(true);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await onPublish(activate);
    } catch {
      // Handled by parent
    }
  };

  const validationReport = getValidationReportFromError(error);
  const errorMessage = !validationReport && error ? getRubricOperationError(error) : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="publish-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-lg rounded-sm border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border p-4 bg-surface-subtle">
          <div>
            <h2
              id="publish-modal-title"
              className="text-sm font-bold uppercase tracking-wider text-text"
            >
              Publish Revision v{versionNumber}
            </h2>
            <p className="text-xs text-text-muted font-medium">Agent: {agentLabel}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="inline-flex size-8 items-center justify-center rounded-sm text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close publish dialog"
          >
            <X className="size-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 grid gap-4">
          <div className="flex items-start gap-3 rounded-sm border border-warning/40 bg-warning-soft p-3 text-xs text-text">
            <AlertTriangle className="size-5 shrink-0 text-warning mt-0.5" aria-hidden="true" />
            <div>
              <p className="font-bold text-text">Important Immutability Notice</p>
              <p className="mt-1 text-text-muted font-medium">
                Publishing will lock this revision permanently. Its domains, criteria, and strategy
                configurations cannot be edited or deleted once published.
              </p>
            </div>
          </div>

          <div className="rounded-sm border border-border bg-surface-subtle p-3">
            <label className="flex items-start gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={activate}
                onChange={(e) => setActivate(e.target.checked)}
                disabled={isPending}
                className="mt-0.5 size-4 rounded border-input text-primary focus:ring-ring"
              />
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-text">
                  Activate Revision Immediately (Recommended)
                </span>
                <p className="text-[11px] text-text-muted font-medium mt-0.5">
                  Point the live evaluation system for {agentLabel} to this new revision. You can
                  roll back to a prior published revision at any time.
                </p>
              </div>
            </label>
          </div>

          {validationReport && <ValidationReportCard report={validationReport} />}

          {errorMessage && (
            <div
              role="alert"
              className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive"
            >
              {errorMessage}
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
              disabled={isPending}
              className="inline-flex h-9 items-center justify-center gap-1.5 px-4 rounded-sm bg-primary text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              {isPending && <Loader2 className="size-3.5 animate-spin" />}
              {activate ? 'Publish and Activate' : 'Publish Only'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
