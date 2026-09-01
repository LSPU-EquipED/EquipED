import { useEffect } from 'react';
import { Spinner, Trash, Warning, X } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';

interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'destructive' | 'primary';
  isPending?: boolean;
}

export function ConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = 'Yes, Delete',
  cancelLabel = 'Cancel',
  variant = 'destructive',
  isPending = false,
}: ConfirmationModalProps) {
  // Close on Escape key press
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

  const isDestructive = variant === 'destructive';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
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
            <div
              className={`flex size-8 items-center justify-center rounded-sm shrink-0 border ${
                isDestructive
                  ? 'bg-destructive-soft text-destructive border-destructive/25'
                  : 'bg-primary-soft text-primary border-primary/25'
              }`}
            >
              {isDestructive ? (
                <Trash className="size-4" aria-hidden="true" />
              ) : (
                <Warning className="size-4" aria-hidden="true" />
              )}
            </div>
            <h2
              id="confirm-modal-title"
              className="text-sm sm:text-base font-bold text-text tracking-tight"
            >
              {title}
            </h2>
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
        <form onSubmit={handleConfirm} className="p-5 sm:p-6 space-y-5">
          <p className="text-xs sm:text-sm text-text-muted leading-relaxed">
            {description}
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
              {cancelLabel}
            </Button>
            <Button
              type="submit"
              variant={isDestructive ? 'destructive' : 'primary'}
              size="md"
              disabled={isPending}
              isLoading={isPending}
              className="text-xs h-9 px-4 font-semibold"
            >
              {isPending ? (
                <>
                  <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                  <span>Processing…</span>
                </>
              ) : (
                <span>{confirmLabel}</span>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
