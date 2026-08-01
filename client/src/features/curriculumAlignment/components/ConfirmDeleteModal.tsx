// client/src/features/curriculumAlignment/components/ConfirmDeleteModal.tsx
// No shared confirm-modal primitive exists yet (every delete confirmation
// elsewhere in the app -- e.g. admin/pages/UserManagementPage.tsx -- still
// uses window.confirm), so this is a local, self-contained modal rather
// than a shared/ promotion (CLAUDE.md: promote to shared/ once 2+ features
// use it). Focus-trap/Escape handling mirrors auth/components/
// ResetPasswordModal.tsx's existing pattern for consistency.
import { useEffect, useRef } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-delete-title"
    >
      <div
        ref={modalRef}
        className="relative w-full max-w-md rounded-sm border border-slate-200 bg-white p-6 shadow-none sm:p-8"
      >
        <div className="mb-4 flex items-center gap-2 text-[#b91c1c]">
          <AlertTriangle className="size-5 shrink-0" />
          <h3
            id="confirm-delete-title"
            className="text-lg font-bold uppercase tracking-wider text-slate-900"
          >
            {title}
          </h3>
        </div>
        <p className="mb-4 text-sm font-medium leading-relaxed text-slate-600">{message}</p>
        {errorMessage ? (
          <div className="mb-4 flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 px-3 py-2 text-xs font-semibold text-[#b91c1c]">
            <AlertTriangle className="size-3.5 shrink-0" />
            {errorMessage}
          </div>
        ) : null}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="h-10 rounded-sm border border-slate-200 px-4 text-xs font-bold uppercase tracking-wider text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-sm bg-[#b91c1c] px-4 text-xs font-bold uppercase tracking-wider text-white transition-colors hover:bg-[#b91c1c]/90 focus:outline-none focus:ring-2 focus:ring-[#b91c1c] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? <Loader2 className="size-3.5 animate-spin" /> : null}
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
