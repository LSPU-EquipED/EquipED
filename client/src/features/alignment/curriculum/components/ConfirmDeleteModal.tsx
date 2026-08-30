// No shared confirm-modal primitive exists yet (every delete confirmation
// elsewhere in the app -- e.g. admin/pages/UserManagementPage.tsx -- still
// uses window.confirm), so this is a local, self-contained modal rather
// than a shared/ promotion (CLAUDE.md: promote to shared/ once 2+ features
// use it). Focus-trap/Escape handling mirrors auth/components/
// ResetPasswordModal.tsx's existing pattern for consistency.
import { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/shared/components/Button';

type ConfirmDeleteModalProps = {
  title: string;
  message: string;
  isPending: boolean;
  errorMessage?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDeleteModal({
  title,
  message,
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: ConfirmDeleteModalProps) {
  const modalRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const modal = modalRef.current;
    if (!modal) return;

    const focusableElements = modal.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );

    if (focusableElements.length > 0) {
      setTimeout(() => focusableElements[0].focus(), 50);
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
        return;
      }

      if (e.key === 'Tab') {
        const focusables = Array.from(focusableElements);
        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            last.focus();
            e.preventDefault();
          }
        } else {
          if (document.activeElement === last) {
            first.focus();
            e.preventDefault();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-delete-title"
    >
      <div
        ref={modalRef}
        className="relative w-full max-w-md rounded-md border border-border bg-surface p-6 shadow-none sm:p-8"
      >
        <div className="mb-4 flex items-center gap-2 text-destructive">
          <AlertTriangle className="size-5 shrink-0" />
          <h3
            id="confirm-delete-title"
            className="text-lg font-bold text-text"
          >
            {title}
          </h3>
        </div>
        <p className="mb-4 text-sm font-normal leading-relaxed text-text-muted">{message}</p>
        {errorMessage ? (
          <div className="mb-4 flex items-center gap-2 rounded-sm border border-destructive/20 bg-destructive-soft px-3 py-2 text-xs font-semibold text-destructive">
            <AlertTriangle className="size-3.5 shrink-0" />
            {errorMessage}
          </div>
        ) : null}
        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={onCancel}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="md"
            onClick={onConfirm}
            disabled={isPending}
            isLoading={isPending}
          >
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}
