import { useEffect, useRef } from 'react';
import { X } from '@phosphor-icons/react';
import { Button, cn, usePresence } from '@equiped/ui';

interface ResetPasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ResetPasswordModal({
  isOpen,
  onClose,
}: ResetPasswordModalProps) {
  const modalRef = useRef<HTMLDivElement | null>(null);
  const { isMounted, isAnimating } = usePresence({ isOpen, durationMs: 180 });

  useEffect(() => {
    if (!isOpen || !isMounted) return;
    const modal = modalRef.current;
    if (!modal) return;
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusables = Array.from(
      modal.querySelectorAll<HTMLElement>('button:not([disabled])'),
    );
    const focusTimer = window.setTimeout(() => focusables[0]?.focus(), 0);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
      if (event.key === 'Tab') {
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            !modal.contains(document.activeElement))
        ) {
          event.preventDefault();
          last?.focus();
        } else if (
          !event.shiftKey &&
          (document.activeElement === last ||
            !modal.contains(document.activeElement))
        ) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [isOpen, isMounted, onClose]);

  if (!isMounted) return null;

  return (
    <div
      role="dialog"
      aria-modal={isOpen ? true : undefined}
      aria-hidden={!isOpen || undefined}
      {...(!isOpen ? ({ inert: '' } as { inert: string }) : {})}
      aria-labelledby="reset-dialog-title"
      aria-describedby="reset-dialog-description"
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 transition-opacity duration-180 ease-out motion-reduce:transition-none',
        isAnimating ? 'opacity-100' : 'pointer-events-none opacity-0',
      )}
    >
      <div
        ref={modalRef}
        className={cn(
          'w-full max-w-md rounded-md border border-border bg-surface',
          isAnimating ? 'animate-ledger-modal-in' : 'animate-ledger-modal-out',
        )}
      >
        <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-3">
          <h2
            id="reset-dialog-title"
            className="text-base font-semibold text-text"
          >
            Reset password
          </h2>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close dialog"
            title="Close dialog"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>
        <div
          className="space-y-3 p-5 text-sm leading-relaxed text-text-muted"
          id="reset-dialog-description"
        >
          <p>
            Password resets require verification by the Campus Institutional
            Administrator.
          </p>
          <p>
            Contact your Department Chair or College Dean’s Office through
            official university channels to request a reset.
          </p>
        </div>
        <div className="flex justify-end px-5 pb-5">
          <Button type="button" onClick={onClose}>
            Got it
          </Button>
        </div>
      </div>
    </div>
  );
}
