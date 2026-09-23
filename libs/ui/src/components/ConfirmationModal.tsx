import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Trash, Warning, WarningCircle } from '@phosphor-icons/react';
import { Button } from './Button';
import { cn } from '../utils';
import { usePresence } from '../hooks/usePresence';

const activeModals: HTMLElement[] = [];

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const selector = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"]):not([disabled])',
  ].join(',');

  return Array.from(container.querySelectorAll<HTMLElement>(selector)).filter(
    (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true' && el.tabIndex !== -1,
  );
}

export interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'destructive' | 'warning' | 'primary';
  isPending?: boolean;
  error?: string | null;
}

export function ConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Cancel',
  variant = 'destructive',
  isPending = false,
  error = null,
}: ConfirmationModalProps) {
  const { isMounted, isAnimating } = usePresence({ isOpen, durationMs: 180 });
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);
  const wasOpenRef = useRef(false);
  const [internalError, setInternalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isEffectivelyPending = isPending || isSubmitting;
  const activeError = error ?? internalError;

  // Clear fallback error when modal closes/reopens
  useEffect(() => {
    if (!isOpen) {
      setInternalError(null);
    }
  }, [isOpen]);

  // Manage previous active element and active modal stack
  useEffect(() => {
    if (isOpen && !wasOpenRef.current) {
      if (document.activeElement instanceof HTMLElement) {
        previousActiveElementRef.current = document.activeElement;
      }
    }
    wasOpenRef.current = isOpen;
  }, [isOpen]);

  // Only open dialogs participate in modality; exiting content remains rendered for its animation.
  useEffect(() => {
    const dialogEl = dialogRef.current;
    if (!isOpen || !isMounted || !dialogEl) return;
    activeModals.push(dialogEl);
    return () => {
      const index = activeModals.indexOf(dialogEl);
      if (index !== -1) activeModals.splice(index, 1);
    };
  }, [isOpen, isMounted]);

  // Initial focus into dialog once mounted and isOpen
  useEffect(() => {
    if (!isOpen || !isMounted) return;

    const focusTimer = requestAnimationFrame(() => {
      const dialog = dialogRef.current;
      if (!dialog || activeModals[activeModals.length - 1] !== dialog) return;
      if (isEffectivelyPending) {
        dialog.focus();
      } else if (cancelButtonRef.current && !cancelButtonRef.current.disabled) {
        cancelButtonRef.current.focus();
      } else {
        dialog.focus();
      }
    });

    return () => cancelAnimationFrame(focusTimer);
  }, [isOpen, isMounted, isEffectivelyPending]);

  // Restore focus when closing or unmounting
  useEffect(() => {
    if (!isOpen) {
      const priorElement = previousActiveElementRef.current;
      const activeDialog = activeModals[activeModals.length - 1];
      if (activeDialog) {
        if (priorElement && activeDialog.contains(priorElement)) priorElement.focus();
        else {
          const focusable = getFocusableElements(activeDialog)[0];
          (focusable ?? activeDialog).focus();
        }
        previousActiveElementRef.current = null;
      } else if (priorElement && document.contains(priorElement)) {
        priorElement.focus();
        previousActiveElementRef.current = null;
      }
    }
  }, [isOpen]);

  useEffect(() => {
    return () => {
      const priorElement = previousActiveElementRef.current;
      const activeDialog = activeModals[activeModals.length - 1];
      if (activeDialog) {
        const focusable = getFocusableElements(activeDialog)[0];
        (focusable ?? activeDialog).focus();
      } else if (priorElement && document.contains(priorElement)) {
        priorElement.focus();
      }
    };
  }, []);

  // Keyboard navigation: Escape and Tab trap
  useEffect(() => {
    if (!isOpen || !isMounted) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const dialogEl = dialogRef.current;
      if (!dialogEl) return;

      // Only handle events if this is the topmost/active modal in the stack
      const isTopModal = activeModals.length === 0 || activeModals[activeModals.length - 1] === dialogEl;
      if (!isTopModal) return;

      if (e.key === 'Escape') {
        if (!isEffectivelyPending) {
          e.preventDefault();
          onClose();
        }
        return;
      }

      if (e.key === 'Tab') {
        const focusableElements = getFocusableElements(dialogEl);
        if (focusableElements.length === 0) {
          e.preventDefault();
          return;
        }

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        const activeEl = document.activeElement;

        if (e.shiftKey) {
          if (activeEl === firstElement || !dialogEl.contains(activeEl)) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (activeEl === lastElement || !dialogEl.contains(activeEl)) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isMounted, isEffectivelyPending, onClose]);

  if (!isMounted) return null;

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isPending || isSubmitting) return;

    setInternalError(null);
    setIsSubmitting(true);
    try {
      await onConfirm();
    } catch {
      // If caller does not provide an external error prop, display fallback error message
      setInternalError('An error occurred while processing this action. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDestructive = variant === 'destructive';
  const isWarning = variant === 'warning';

  const defaultConfirmLabel = isDestructive
    ? 'Delete'
    : isWarning
      ? 'Confirm'
      : 'Continue';

  return (
    <div
      ref={dialogRef}
      role="dialog"
      tabIndex={-1}
      aria-modal={isOpen ? 'true' : undefined}
      aria-hidden={isOpen ? undefined : true}
      {...(!isOpen ? { inert: '' } as { inert: string } : {})}
      aria-labelledby={titleId}
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 transition-opacity duration-180 ease-out backdrop-blur-xs',
        isAnimating ? 'opacity-100' : 'opacity-0 pointer-events-none',
      )}
      onClick={() => {
        if (!isEffectivelyPending) onClose();
      }}
    >
      <div
        className={cn(
          'w-full max-w-md rounded-md border border-border bg-surface shadow-xl overflow-hidden',
          isAnimating ? 'animate-ledger-modal-in' : 'animate-ledger-modal-out',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar with distinct semantic accent badge */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border bg-surface-subtle/50">
          <div
            className={cn(
              'flex size-8.5 items-center justify-center rounded-sm shrink-0 border',
              isDestructive && 'bg-destructive-soft text-destructive border-destructive/25',
              isWarning && 'bg-warning-soft text-warning border-warning/30',
              !isDestructive && !isWarning && 'bg-primary-soft text-primary border-primary/25',
            )}
          >
            {isDestructive ? (
              <Trash className="size-4" aria-hidden="true" />
            ) : isWarning ? (
              <Warning className="size-4" aria-hidden="true" />
            ) : (
              <WarningCircle className="size-4" aria-hidden="true" />
            )}
          </div>
          <h2
            id={titleId}
            className="text-sm sm:text-base font-semibold text-text tracking-tight"
          >
            {title}
          </h2>
        </div>

        {/* Content & Action Buttons */}
        <form onSubmit={handleConfirm} className="p-5 sm:p-6">
          <div className="text-xs sm:text-sm text-text-muted leading-relaxed">
            {description}
          </div>

          {activeError && (
            <div
              role="alert"
              className="mt-3 rounded-sm border border-destructive/30 bg-destructive-soft px-3.5 py-2.5 text-xs font-medium text-destructive flex items-center gap-2"
            >
              <WarningCircle className="size-4 shrink-0" aria-hidden="true" />
              <span>{activeError}</span>
            </div>
          )}

          <div className="mt-6 flex items-center justify-end gap-2.5">
            <Button
              ref={cancelButtonRef}
              type="button"
              variant="secondary"
              size="md"
              onClick={onClose}
              disabled={isEffectivelyPending}
              className="text-xs h-9 px-4 font-semibold"
            >
              {cancelLabel}
            </Button>
            <Button
              ref={confirmButtonRef}
              type="submit"
              variant={isDestructive ? 'destructive' : 'primary'}
              size="md"
              disabled={isEffectivelyPending}
              isLoading={isEffectivelyPending}
              className={cn(
                'text-xs h-9 px-4 font-semibold gap-1.5',
                isWarning && 'bg-amber-600 hover:bg-amber-700 text-white focus-visible:ring-amber-500 border-transparent',
              )}
            >
              <span>{isEffectivelyPending ? 'Processing…' : (confirmLabel || defaultConfirmLabel)}</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
