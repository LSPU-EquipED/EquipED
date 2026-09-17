import { useEffect, useState } from 'react';
import { ArrowSquareOut, Check, Copy, FileText, Spinner, X } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import { cn, usePresence } from '@equiped/ui';
import type { ClientDocument, LatestEvaluationItem, TargetAgent } from '@equiped/types';
import {
  getSlmDisplayStatus,
  type SlmStatusQueryState,
} from '@/shared/utils/slmDisplayStatus';
import {
  truncateId,
  formatProcessingStatus,
  getHumanReadableTitle,
  getEvaluationDescription,
  getEvaluationActionLabel,
  formatInspectorDate,
} from '../utils/moduleInspector.utils';
import { useClipboardCopy } from '../hooks/useClipboardCopy';

interface ModuleInspectorDrawerProps {
  document: ClientDocument | null;
  latestEvaluation?: LatestEvaluationItem;
  latestEvalsState?: SlmStatusQueryState;
  targetAgent?: TargetAgent;
  onClose: () => void;
}

export function ModuleInspectorDrawer({
  document,
  latestEvaluation,
  latestEvalsState,
  targetAgent = 'sme',
  onClose,
}: ModuleInspectorDrawerProps) {
  const isOpen = Boolean(document);
  const { isMounted, isAnimating } = usePresence({ isOpen, durationMs: 240 });
  const [lastDoc, setLastDoc] = useState<ClientDocument | null>(document);
  const { copiedValue, copy } = useClipboardCopy({ resetTimeoutMs: 2000 });

  // Retain the last document while the drawer exit animation completes.
  useEffect(() => {
    if (document) {
      setLastDoc(document);
    }
  }, [document]);

  const cachedDoc = document ?? lastDoc;

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isMounted) {
      window.addEventListener('keydown', handleKey);
      return () => window.removeEventListener('keydown', handleKey);
    }
  }, [isMounted, onClose]);

  if (!isMounted || !cachedDoc) return null;

  const outline = cachedDoc.structuredOutline ?? [];
  const slmDisplay = getSlmDisplayStatus(
    cachedDoc,
    latestEvaluation,
    latestEvalsState,
    targetAgent,
  );

  const humanReadableTitle = getHumanReadableTitle(cachedDoc);

  const handleCopyId = () => {
    if (!cachedDoc?.documentId) return;
    void copy(cachedDoc.documentId);
  };

  const isCopied = Boolean(cachedDoc.documentId && copiedValue === cachedDoc.documentId);

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex justify-end bg-foreground/40 transition-opacity duration-240 ease-out overflow-hidden',
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
          'w-full max-w-xl h-full bg-surface border-l border-border shadow-xl flex flex-col overflow-hidden',
          isAnimating ? 'animate-ledger-drawer-in' : 'animate-ledger-drawer-out',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5 bg-surface shrink-0">
          <div className="min-w-0 flex-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Module Details
            </span>
            <h2
              className="text-base sm:text-lg font-bold text-text truncate mt-1 leading-snug"
              title={humanReadableTitle}
            >
              {humanReadableTitle}
            </h2>
            {cachedDoc.title !== humanReadableTitle && (
              <p
                className="font-mono text-xs text-text-muted truncate mt-0.5"
                title={cachedDoc.title}
              >
                {cachedDoc.title}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2 mt-2.5">
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
            className="rounded-md p-1.5 text-text-muted hover:text-text hover:bg-surface-subtle border border-transparent hover:border-border transition-colors cursor-pointer shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4.5" aria-hidden="true" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Section 1: Document Information */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Document Information
            </h3>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <span className="text-[11px] font-medium text-text-muted block">Total Pages</span>
                <span className="font-mono text-sm font-semibold text-text tabular-nums mt-0.5 block truncate">
                  {cachedDoc.pageCount != null ? cachedDoc.pageCount : 'Not specified'}
                </span>
              </div>
              <div>
                <span className="text-[11px] font-medium text-text-muted block">Text Format</span>
                <span className="text-sm font-semibold text-text mt-0.5 block truncate">
                  {cachedDoc.hasOcrPages ? 'Scanned PDF' : 'Searchable PDF'}
                </span>
              </div>
              <div>
                <span className="text-[11px] font-medium text-text-muted block">Processing Status</span>
                <span className="text-sm font-semibold text-text mt-0.5 block truncate">
                  {formatProcessingStatus(cachedDoc.processingStatus)}
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Academic Information */}
          <div className="space-y-3 pt-6 border-t border-border/60">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Academic Information
            </h3>

            <dl className="grid grid-cols-2 gap-x-6 gap-y-3.5 pt-0.5">
              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Course Title</dt>
                <dd
                  className="font-semibold text-text text-sm truncate"
                  title={cachedDoc.courseTitle || undefined}
                >
                  {cachedDoc.courseTitle || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Lesson / Unit</dt>
                <dd
                  className="font-semibold text-text text-sm truncate"
                  title={cachedDoc.lessonTitle || undefined}
                >
                  {cachedDoc.lessonTitle || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Academic Program</dt>
                <dd className="font-semibold text-text text-sm">
                  {cachedDoc.program || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Course Code</dt>
                <dd className="font-mono font-semibold text-text text-sm">
                  {cachedDoc.courseCode || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Academic Year</dt>
                <dd className="font-semibold text-text text-sm">
                  {cachedDoc.academicYear || 'Not specified'}
                </dd>
              </div>

              <div className="space-y-0.5">
                <dt className="text-[11px] font-medium text-text-muted">Uploaded Date</dt>
                <dd className="font-medium text-text text-sm tabular-nums">
                  {formatInspectorDate(cachedDoc.uploadedAt)}
                </dd>
              </div>
            </dl>
          </div>

          {/* Section 3: Multi-Agent Evaluation */}
          <div className="space-y-3 pt-6 border-t border-border/60">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Multi-Agent Evaluation
            </h3>

            <p className="text-xs text-text-muted leading-relaxed">
              {getEvaluationDescription(slmDisplay.actionType)}
            </p>

            {slmDisplay.isClickable && slmDisplay.actionUrl && (
              <div>
                <Link
                  to={slmDisplay.actionUrl}
                  className="inline-flex items-center gap-2 rounded-sm bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary-hover transition-colors shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
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
          <div className="space-y-3 pt-6 border-t border-border/60">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Document File
            </h3>

            <div className="flex items-center justify-between gap-3 rounded-md bg-surface-subtle border border-border p-3.5">
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
                  onClick={handleCopyId}
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
            <div className="space-y-2.5 pt-6 border-t border-border/60">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Module Outline
                </h3>
                <span className="text-xs text-text-muted font-mono">
                  {outline.length} {outline.length === 1 ? 'section' : 'sections'}
                </span>
              </div>

              <div className="rounded-md border border-border bg-surface divide-y divide-border/60 overflow-hidden text-xs max-h-56 overflow-y-auto">
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
