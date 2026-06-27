import { useEffect, useRef } from 'react';

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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reset-dialog-title"
    >
      <div
        ref={modalRef}
        className="w-full max-w-md bg-white border border-slate-200 p-6 sm:p-8 rounded-none shadow-none relative"
      >
        <h3
          id="reset-dialog-title"
          className="text-lg font-bold text-slate-900 mb-3 uppercase tracking-wider"
        >
          Password Reset Request
        </h3>
        <p className="text-sm text-slate-600 leading-relaxed mb-6 font-medium">
          Password resets must be requested directly through the LSPU IT Support Office (ITSO).
          Please visit their office or contact them via official channels to recover your
          credentials.
        </p>
        <button
          type="button"
          className="w-full h-12 rounded-none bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white font-bold text-[13px] tracking-[0.1em] uppercase transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </div>
  );
}
