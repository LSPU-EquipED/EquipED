import { useEffect, useRef, useState } from 'react';
import { X } from '@phosphor-icons/react';
import { Badge, cn, usePresence } from '@equiped/ui';
import type { ModelValidationItem } from '../types';
import { adapterFallbackNotices, formatTimestamp, itemModelLabel } from '../utils/helpers';
import { ValidationDetail } from './ValidationDetail';

export function ValidationReviewPanel({
  item,
  onClose,
}: {
  item: ModelValidationItem;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [isOpen, setIsOpen] = useState(true);
  const { isMounted, isAnimating } = usePresence({ isOpen, durationMs: 240 });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const trigger = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
    };
  }, []);

  useEffect(() => {
    if (!isMounted) onClose();
  }, [isMounted, onClose]);

  return (
    <dialog
      ref={dialogRef}
      id={`validation-review-${item.validation_id}`}
      aria-label={`Validation details for ${item.document_title ?? 'Untitled SLM'}`}
      aria-modal="true"
      onCancel={(event) => {
        event.preventDefault();
        setIsOpen(false);
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) setIsOpen(false);
      }}
      className={cn(
        'fixed inset-0 m-0 h-dvh max-h-none w-screen max-w-none border-0 bg-transparent p-0 text-text backdrop:bg-overlay/40 backdrop:transition-opacity backdrop:duration-240 backdrop:ease-out open:flex open:justify-end',
        !isAnimating && 'backdrop:opacity-0',
      )}
    >
      <div
        className={cn(
          'flex h-full w-full max-w-3xl flex-col overflow-hidden border-l border-border bg-canvas',
          isAnimating ? 'animate-ledger-drawer-in' : 'animate-ledger-drawer-out',
        )}
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border bg-canvas px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-primary">Validation review</p>
            <h2 className="mt-1 text-lg font-semibold leading-snug text-text [overflow-wrap:anywhere]">
              {item.document_title ?? 'Untitled SLM'}
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
              <Badge
                variant={
                  item.status === 'COMPLETED'
                    ? 'success'
                    : item.status === 'FAILED'
                      ? 'destructive'
                      : 'warning'
                }
                withDot
              >
                {item.status.charAt(0) + item.status.slice(1).toLowerCase()}
              </Badge>
              <span className="font-mono tabular-nums">{formatTimestamp(item.created_at)}</span>
              {itemModelLabel(item) ? (
                <span className="rounded-xs border border-border bg-surface-subtle px-1.5 py-0.5 font-semibold text-text">
                  {itemModelLabel(item)}
                </span>
              ) : null}
              {item.partial_without_curriculum ? (
                <span className="font-medium text-warning">Partial run</span>
              ) : null}
            </div>
            {adapterFallbackNotices(item.adapter_resolution).map((notice) => (
              <p key={notice} className="mt-2 text-[11px] font-medium text-warning">
                {notice}
              </p>
            ))}
          </div>
          <button
            type="button"
            aria-label="Close validation details"
            onClick={() => setIsOpen(false)}
            disabled={!isOpen}
            className="inline-flex size-9 shrink-0 items-center justify-center rounded-sm border border-border bg-surface text-text-muted transition-colors hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-5 sm:p-6">
          <ValidationDetail
            id={`validation-detail-${item.validation_id}`}
            validationId={item.validation_id}
            fallbackCriteria={item.criterion_scores}
            boundForms={item.bound_forms}
            partialWithoutCurriculum={item.partial_without_curriculum}
            overallStatus={item.status}
            errorMessage={item.error_message}
            isExpanded={isOpen}
          />
        </div>
      </div>
    </dialog>
  );
}
