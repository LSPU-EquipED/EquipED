import { AlertTriangle, X } from 'lucide-react';
import { useEffect, useRef } from 'react';

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
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/55 p-4" role="presentation">
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="replace-alignment-title"
        aria-describedby="replace-alignment-description"
        className="w-full max-w-md border border-slate-300 bg-white"
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-5 text-[#b91c1c]" aria-hidden="true" />
            <h2 id="replace-alignment-title" className="text-lg font-bold text-slate-950">
              Replace the current result?
            </h2>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="grid size-8 place-items-center border border-slate-300 text-slate-700 disabled:opacity-50"
            aria-label="Close confirmation"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="p-4">
          <p id="replace-alignment-description" className="text-sm leading-6 text-slate-700">
            This SLM already has a stored syllabus-alignment result. Evaluating it again will
            permanently replace that result in the database. The previous result cannot be viewed
            afterward.
          </p>
        </div>
        <footer className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 p-4">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="h-9 border border-slate-300 bg-white px-4 text-xs font-bold uppercase tracking-wide text-slate-700 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            autoFocus
            className="h-9 bg-[#b91c1c] px-4 text-xs font-bold uppercase tracking-wide text-white disabled:opacity-50"
          >
            {busy ? 'Replacing…' : 'Replace and evaluate'}
          </button>
        </footer>
      </section>
    </div>
  );
}
