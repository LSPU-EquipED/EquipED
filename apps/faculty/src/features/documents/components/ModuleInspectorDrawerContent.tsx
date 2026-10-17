import type { RefObject } from "react";
import { Check, Copy, X } from "@phosphor-icons/react";
import { cn } from "@equiped/ui";
import type { ClientDocument } from "@equiped/types";
import {
  truncateId,
  formatProcessingStatus,
  formatInspectorDate,
} from "../utils/moduleInspector.utils";

export interface ModuleInspectorDrawerContentProps {
  isOpen: boolean;
  isAnimating: boolean;
  cachedDoc: ClientDocument;
  humanReadableTitle: string;
  outline: NonNullable<ClientDocument["structuredOutline"]>;
  isCopied: boolean;
  onClose: () => void;
  onCopyId: () => void;
  dialogRef: RefObject<HTMLDivElement>;
}

export function ModuleInspectorDrawerContent({
  isOpen,
  isAnimating,
  cachedDoc,
  humanReadableTitle,
  outline,
  isCopied,
  onClose,
  onCopyId,
  dialogRef,
}: ModuleInspectorDrawerContentProps) {
  const academic = [
    ["Program", cachedDoc.program],
    ["Course code", cachedDoc.courseCode],
    ["Academic year", cachedDoc.academicYear],
    ["Uploaded", formatInspectorDate(cachedDoc.uploadedAt)],
  ].filter(([, value]) => Boolean(value));
  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex justify-end overflow-hidden",
        !isOpen && "pointer-events-none",
      )}
      onClick={onClose}
      aria-hidden={!isOpen}
    >
      <div
        aria-hidden="true"
        className={cn(
          "absolute inset-0 bg-overlay/45 transition-opacity duration-240 ease-out",
          isAnimating ? "opacity-100" : "opacity-0",
        )}
      />
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`Module details: ${cachedDoc.title}`}
        className={cn(
          "relative flex h-full w-full max-w-xl flex-col border-l border-border bg-surface focus:outline-none",
          isOpen ? "animate-ledger-drawer-in" : "animate-ledger-drawer-out",
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-5 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs font-medium text-text-muted">
              Module details
            </p>
            <h2 className="mt-2 break-words text-lg font-semibold leading-relaxed text-text">
              {humanReadableTitle}
            </h2>
            {cachedDoc.title !== humanReadableTitle && (
              <p className="mt-1 break-words text-xs leading-relaxed text-text-muted">
                {cachedDoc.title}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close module details"
            title="Close"
            className="inline-flex size-10 shrink-0 items-center justify-center rounded-sm text-text-muted hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-6 sm:px-6">
          <section aria-label="Academic details">
            <h3 className="text-sm font-semibold text-text">
              Academic details
            </h3>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4">
              {academic.map(([label, value]) => (
                <div key={label}>
                  <dt className="text-xs text-text-muted">{label}</dt>
                  <dd className="mt-1 break-words text-sm font-medium text-text">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
          <section
            aria-label="File details"
            className="border-t border-border pt-6"
          >
            <h3 className="text-sm font-semibold text-text">File details</h3>
            <dl className="mt-4 space-y-3">
              {[
                [
                  "Pages",
                  cachedDoc.pageCount != null
                    ? `${cachedDoc.pageCount} pages`
                    : "Not provided",
                ],
                [
                  "Text format",
                  cachedDoc.hasOcrPages ? "Scanned PDF" : "Searchable PDF",
                ],
                [
                  "Processing status",
                  formatProcessingStatus(cachedDoc.processingStatus),
                ],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1"
                >
                  <dt className="text-xs text-text-muted">{label}</dt>
                  <dd className="text-sm font-medium tabular-nums text-text">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
          {outline.length > 0 && (
            <section className="border-t border-border pt-6">
              <h3 className="text-sm font-semibold text-text">
                Module outline{" "}
                <span className="ml-2 text-xs font-normal tabular-nums text-text-muted">
                  {outline.length}{" "}
                  {outline.length === 1 ? "section" : "sections"}
                </span>
              </h3>
              <ol className="mt-3 divide-y divide-border">
                {outline.map((item, index) => (
                  <li key={index} className="py-3">
                    <p className="text-sm font-medium text-text">
                      {String(
                        item.title || item.name || `Section ${index + 1}`,
                      )}
                    </p>
                    {Boolean(item.description) && (
                      <p className="mt-1 text-sm leading-relaxed text-text-muted">
                        {String(item.description)}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            </section>
          )}
          <details className="border-t border-border pt-5">
            <summary className="w-fit cursor-pointer rounded-sm text-xs font-medium text-text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
              Technical details
            </summary>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs text-text-muted">Document ID</span>
              <div className="flex items-center gap-2">
                <span
                  className="font-mono text-xs text-text-muted"
                  title={cachedDoc.documentId}
                >
                  {truncateId(cachedDoc.documentId)}
                </span>
                <button
                  type="button"
                  onClick={onCopyId}
                  aria-label="Copy document ID"
                  title="Copy complete document ID"
                  className="inline-flex min-h-10 items-center gap-1 rounded-sm px-2 text-xs text-primary hover:bg-primary-soft focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {isCopied ? (
                    <Check className="size-3.5" aria-hidden="true" />
                  ) : (
                    <Copy className="size-3.5" aria-hidden="true" />
                  )}
                  {isCopied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
