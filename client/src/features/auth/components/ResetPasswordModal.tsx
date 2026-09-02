import { useEffect, useRef } from 'react';
import { X } from '@phosphor-icons/react';
interface ResetPasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}
export function ResetPasswordModal({ isOpen, onClose }: ResetPasswordModalProps) {
  const modalRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;

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
        onClose();
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
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reset-dialog-title"
    >
      <div
        ref={modalRef}
        className="w-full max-w-md bg-white border border-slate-200 p-6 sm:p-7 rounded-sm shadow-xl relative animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Modal Header */}
        <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-200">
          <div>
            <h3
              id="reset-dialog-title"
              className="text-base font-bold text-slate-900 tracking-tight"
            >
              Password Reset Protocol
            </h3>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Institutional Account Recovery Procedure
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="size-8 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-sm transition-colors flex items-center justify-center cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
            aria-label="Close dialog"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="py-4 space-y-3.5 text-sm text-slate-600 leading-relaxed">
          <p>
            To preserve faculty evaluation audit integrity, direct self-service password resets are restricted. Password resets must be verified through the Campus Institutional Administrator.
          </p>
          <p className="text-xs text-slate-500 pt-3 border-t border-slate-100">
            Please contact your Department Chair or College Dean's Office via official university channels to request credential recovery.
          </p>
        </div>

        {/* Modal Footer */}
        <div className="pt-3.5 border-t border-slate-200 flex justify-end">
          <button
            type="button"
            className="h-10 px-5 rounded-sm bg-[#1b3b87] hover:bg-[#142f70] active:bg-[#0f2354] text-white font-bold text-xs tracking-[0.08em] uppercase transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
            onClick={onClose}
          >
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
}
