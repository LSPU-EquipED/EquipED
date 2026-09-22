import { ArrowSquareOut, Check, Copy, FileText, Spinner, X } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import { cn } from '@equiped/ui';
import type { ClientDocument } from '@equiped/types';
import type { SlmDisplayStatus } from '@/shared/utils/slmDisplayStatus';
import {
  truncateId,
  formatProcessingStatus,
  getEvaluationDescription,
  getEvaluationActionLabel,
  formatInspectorDate,
} from '../utils/moduleInspector.utils';

export interface ModuleInspectorDrawerContentProps {
  isOpen: boolean;
  isAnimating: boolean;
  cachedDoc: ClientDocument;
  humanReadableTitle: string;
  slmDisplay: SlmDisplayStatus;
  outline: NonNullable<ClientDocument['structuredOutline']>;
  isCopied: boolean;
  onClose: () => void;
  onCopyId: () => void;
}

export function ModuleInspectorDrawerContent({
  isOpen,
  isAnimating,
  cachedDoc,
  humanReadableTitle,
  slmDisplay,
  outline,
  isCopied,
  onClose,
  onCopyId,
}: ModuleInspectorDrawerContentProps) {
  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex justify-end overflow-hidden bg-foreground/45 backdrop-blur-2xs transition-opacity duration-240 ease-out',
        isAnimating ? 'opacity-100' : 'opacity-0 pointer-events-none',
      )}
      onClick={onClose}
      aria-hidden={!isOpen}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Module details: ${cachedDoc.title}`}
        className={cn(
          'flex h-full w-full max-w-xl flex-col overflow-hidden border-l-2 border-border bg-surface shadow-xl',
          isAnimating ? 'animate-ledger-drawer-in' : 'animate-ledger-drawer-out',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border border-t-2 border-t-primary bg-canvas px-6 py-5 sm:px-7">
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-medium tracking-[0.08em] text-text-muted">
              Module details
            </span>
            <h2
              className="mt-1 break-words text-lg font-semibold leading-snug text-text sm:text-xl"
              title={humanReadableTitle}
            >
              {humanReadableTitle}
            </h2>
            {cachedDoc.title !== humanReadableTitle && (
              <p
                className="mt-1 break-words text-xs text-text-muted"
                title={cachedDoc.title}
              >
                {cachedDoc.title}
              </p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  'inline-flex items-center rounded-xs px-2 py-0.5 text-xs font-semibold select-none',
                  slmDisplay.badgeClass,
                )}
              >
                {slmDisplay.showSpinner && (
                  <Spinner className="mr-1 size-3 animate-spin" aria-hidden="true" />
                )}
                {slmDisplay.badgeLabel}
              </span>
              {cachedDoc.program && (
                <span className="inline-flex items-center rounded-xs border border-border bg-surface-subtle px-2 py-0.5 font-mono text-xs font-semibold text-text select-none">
                  {cachedDoc.program}
                </span>
              )}
              {cachedDoc.courseCode && (
                <span className="inline-flex items-center rounded-xs border border-border bg-surface-subtle px-2 py-0.5 font-mono text-xs font-semibold text-text select-none">
                  {cachedDoc.courseCode}
                </span>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close module details"
            title="Close"
            className="shrink-0 rounded-sm border border-transparent p-1.5 text-text-muted transition-colors hover:border-border hover:bg-surface-subtle hover:text-text cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4.5" aria-hidden="true" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 space-y-7 overflow-y-auto p-6 sm:p-7">
          {/* Section 1: Document Information */}
          <div className="space-y-3">
            <h3 className="text-[11px] font-medium tracking-[0.08em] text-text-muted">
              Document information
            </h3>

            <div className="grid grid-cols-1 divide-y divide-border overflow-hidden rounded-sm border border-border bg-surface sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              <div className="p-3.5">
                <span className="block text-[11px] font-medium text-text-muted">Total pages</span>
                <span className="mt-1 block truncate font-mono text-base font-semibold text-text tabular-nums">
                  {cachedDoc.pageCount != null ? cachedDoc.pageCount : 'Not specified'}
                </span>
              </div>
              <div className="p-3.5">
                <span className="block text-[11px] font-medium text-text-muted">Text format</span>
                <span className="mt-1 block truncate text-sm font-semibold text-text">
                  {cachedDoc.hasOcrPages ? 'Scanned PDF' : 'Searchable PDF'}
                </span>
              </div>
              <div className="p-3.5">
                <span className="block text-[11px] font-medium text-text-muted">Processing status</span>
                <span className="mt-1 block truncate text-sm font-semibold text-text">
                  {formatProcessingStatus(cachedDoc.processingStatus)}
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Academic Information */}
          <div className="space-y-3 border-t border-border/60 pt-7">
            <h3 className="text-[11px] font-medium tracking-[0.08em] text-text-muted">
              Academic information
            </h3>

            <dl className="grid grid-cols-2 gap-x-6 gap-y-3.5 pt-0.5">
              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Course title</dt>
                <dd
                  className="break-words text-sm font-semibold text-text"
                  title={cachedDoc.courseTitle || undefined}
                >
                  {cachedDoc.courseTitle || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Lesson / unit</dt>
                <dd
                  className="break-words text-sm font-semibold text-text"
                  title={cachedDoc.lessonTitle || undefined}
                >
                  {cachedDoc.lessonTitle || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Academic program</dt>
                <dd className="font-semibold text-text text-sm">
                  {cachedDoc.program || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Course code</dt>
                <dd className="font-mono font-semibold text-text text-sm">
                  {cachedDoc.courseCode || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Academic year</dt>
                <dd className="font-semibold text-text text-sm">
                  {cachedDoc.academicYear || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Uploaded date</dt>
                <dd className="font-medium text-text text-sm tabular-nums">
                  {formatInspectorDate(cachedDoc.uploadedAt)}
                </dd>
              </div>
            </dl>
          </div>

          {/* Section 3: Multi-Agent Evaluation */}
          <div className="space-y-3 rounded-sm border border-primary/20 bg-primary-soft/35 p-4">
            <h3 className="text-[11px] font-medium tracking-[0.08em] text-text-muted">
              Multi-agent evaluation
            </h3>

            <p className="text-xs leading-relaxed text-text-muted">
              {getEvaluationDescription(slmDisplay.actionType)}
            </p>

            {slmDisplay.isClickable && slmDisplay.actionUrl && (
              <div className="pt-1">
                <Link
                  to={slmDisplay.actionUrl}
                  className="inline-flex items-center gap-2 rounded-sm bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground shadow-xs transition-colors hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
                >
                  <span>
                    {getEvaluationActionLabel(slmDisplay.actionType, slmDisplay.actionLabel)}
                  </span>
                  <ArrowSquareOut className="size-3.5" aria-hidden="true" />
                </Link>
              </div>
            )}
          </div>

          {/* Section 4: Document File */}
          <div className="space-y-3 border-t border-border/60 pt-7">
            <h3 className="text-[11px] font-medium tracking-[0.08em] text-text-muted">
              Document file
            </h3>

            <div className="flex items-center justify-between gap-3 rounded-sm border border-border bg-surface-subtle p-3.5">
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-surface border border-border text-primary">
                  <FileText className="size-5" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <span className="text-xs font-semibold text-text block truncate">
                    Original PDF Document
                  </span>
                  <span className="text-[11px] text-text-muted block truncate mt-0.5">
                    {cachedDoc.pageCount != null ? `${cachedDoc.pageCount} pages · ` : ''}
                    {cachedDoc.hasOcrPages ? 'Scanned PDF' : 'Searchable PDF'}
                  </span>
                </div>
              </div>

              <a
                href={`/api/v1/documents/${cachedDoc.documentId}/file`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-sm border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text hover:bg-surface-subtle hover:border-primary/50 transition-colors shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span>Open PDF</span>
                <ArrowSquareOut className="size-3.5 text-text-muted" aria-hidden="true" />
              </a>
            </div>

            {/* Document ID */}
            <div className="flex items-center justify-between gap-2 pt-1 text-xs text-text-muted">
              <span className="text-[11px] font-medium">Document ID</span>
              <div className="flex items-center gap-2">
                <span
                  className="font-mono text-[11px] text-text-muted select-all"
                  title={cachedDoc.documentId}
                >
                  {truncateId(cachedDoc.documentId)}
                </span>
                <button
                  type="button"
                  onClick={onCopyId}
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] font-medium text-text-muted hover:text-text rounded-xs hover:bg-surface-subtle transition-colors cursor-pointer"
                  title="Copy complete document ID"
                  aria-label="Copy document ID"
                >
                  {isCopied ? (
                    <>
                      <Check className="size-3 text-success" aria-hidden="true" />
                      <span className="text-success font-semibold">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="size-3" aria-hidden="true" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Section 5: Extracted Outline (Only rendered when real outline data exists) */}
          {outline.length > 0 && (
            <div className="space-y-2.5 border-t border-border/60 pt-7">
              <div className="flex items-center justify-between">
                <h3 className="text-[11px] font-medium tracking-[0.08em] text-text-muted">
                  Module outline
                </h3>
                <span className="text-xs text-text-muted font-mono">
                  {outline.length} {outline.length === 1 ? 'section' : 'sections'}
                </span>
              </div>

              <div className="max-h-56 divide-y divide-border/60 overflow-y-auto overflow-hidden rounded-sm border border-border bg-surface text-xs">
                {outline.map((item, idx) => (
                  <div key={idx} className="p-3 space-y-1">
                    <span className="font-semibold text-text block">
                      {String(item.title || item.name || `Section ${idx + 1}`)}
                    </span>
                    {Boolean(item.description) && (
                      <p className="text-[11px] text-text-muted leading-relaxed">
                        {String(item.description)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
