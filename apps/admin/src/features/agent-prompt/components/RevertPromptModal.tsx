import { useEffect } from 'react';
import { ArrowCounterClockwise, Spinner, X } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';

interface RevertPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void> | void;
  agentLabel: string;
  versionNumber: number;
  isPending?: boolean;
}

export function RevertPromptModal({
  isOpen,
  onClose,
  onConfirm,
  agentLabel,
  versionNumber,
  isPending = false,
}: RevertPromptModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isPending) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isPending, onClose]);

  if (!isOpen) return null;

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await onConfirm();
    } catch {
      // Handled by parent
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="revert-prompt-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
      onClick={() => {
        if (!isPending) onClose();
      }}
    >
      <div
        className="relative w-full max-w-md rounded-md border border-border bg-surface shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border p-4 sm:p-5 bg-surface-subtle">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-sm bg-primary/10 text-primary border border-primary/20 shrink-0">
              <ArrowCounterClockwise className="size-4.5" aria-hidden="true" />
            </div>
            <div>
              <h2
                id="revert-prompt-title"
                className="text-sm sm:text-base font-bold text-text tracking-tight"
              >
                Revert Prompt to v{versionNumber}
              </h2>
              <p className="text-xs text-text-muted font-medium">Agent: {agentLabel}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="inline-flex size-8 items-center justify-center rounded-sm text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
            aria-label="Close dialog"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Content & Action Buttons */}
        <form onSubmit={handleConfirm} className="p-5 sm:p-6 space-y-4">
          <p className="text-xs sm:text-sm text-text-muted leading-relaxed">
            Are you sure you want to revert the system directive for{' '}
            <strong className="text-text font-bold">{agentLabel}</strong> to{' '}
            <strong className="text-text font-bold font-mono">Revision v{versionNumber}</strong>?
          </p>
          <p className="text-[11px] text-text-muted leading-relaxed rounded-sm bg-surface-subtle border border-border p-3">
            This will immediately publish a new active version cloning Revision v{versionNumber},
            which will be used by all subsequent evaluations for this agent.
          </p>

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
              className="text-xs h-9 px-4 font-semibold gap-1.5"
            >
              {isPending ? (
                <>
                  <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                  <span>Reverting…</span>
                </>
              ) : (
                <span>Confirm Revert to v{versionNumber}</span>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
