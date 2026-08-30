import { useEffect, useRef } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/shared/components/Button';

type ReplaceAlignmentModalProps = {
  open: boolean;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ReplaceAlignmentModal({
  open,
  busy,
  onCancel,
  onConfirm,
}: ReplaceAlignmentModalProps) {
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onCancel();
      if (event.key !== 'Tab') return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [busy, onCancel, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="presentation">
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="replace-alignment-title"
        aria-describedby="replace-alignment-description"
        className="w-full max-w-md rounded-md border border-border bg-surface shadow-none overflow-hidden"
      >
        <header className="flex items-start justify-between gap-4 border-b border-border bg-surface p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-5 text-destructive" aria-hidden="true" />
            <h2 id="replace-alignment-title" className="text-lg font-bold text-text">
              Replace the current result?
            </h2>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="inline-flex size-8 items-center justify-center rounded-sm border border-border bg-surface text-text hover:bg-surface-subtle disabled:opacity-50 transition-colors"
            aria-label="Close confirmation"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="p-4">
          <p id="replace-alignment-description" className="text-sm leading-6 text-text-muted">
            This SLM already has a stored syllabus-alignment result. Evaluating it again will
            permanently replace that result in the database. The previous result cannot be viewed
            afterward.
          </p>
        </div>
        <footer className="flex justify-end gap-2 border-t border-border bg-surface-subtle p-4">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={onConfirm}
            disabled={busy}
            isLoading={busy}
            autoFocus
          >
            {busy ? 'Replacing…' : 'Replace and evaluate'}
          </Button>
        </footer>
      </section>
    </div>
  );
}
