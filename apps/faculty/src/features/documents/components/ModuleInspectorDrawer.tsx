import { useEffect } from 'react';
import { ArrowSquareOut, BookOpen, CheckCircle, FileText, Info, X } from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import type { ClientDocument } from '@/shared/types/documents';

interface ModuleInspectorDrawerProps {
  document: ClientDocument | null;
  onClose: () => void;
}

export function ModuleInspectorDrawer({
  document,
  onClose,
}: ModuleInspectorDrawerProps) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  if (!document) return null;

  const outline = document.structuredOutline ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-foreground/30 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Module Technical Inspector: ${document.title}`}
        className="w-full max-w-xl h-full bg-surface border-l border-border shadow-xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-border px-6 py-4 bg-surface-subtle">
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
              SLM Storage Dossier
            </span>
            <h2 className="text-base font-bold text-text truncate mt-0.5" title={document.title}>
              {document.title}
            </h2>
            <div className="flex flex-wrap items-center gap-2 mt-1">
              <Badge variant="info">{document.program || 'No Program'}</Badge>
              {document.courseCode && (
                <span className="font-mono text-xs font-semibold text-text-muted">
                  {document.courseCode}
                </span>
              )}
              {document.pageCount != null && (
                <span className="text-xs text-text-muted font-medium">
                  · {document.pageCount} pages
                </span>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close inspector drawer"
            className="rounded-xs p-1 text-text-muted hover:text-text hover:bg-surface transition-colors cursor-pointer"
          >
            <X className="size-4.5" aria-hidden="true" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* File Actions */}
          <div className="rounded-md border border-border bg-surface-subtle p-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <FileText className="size-6 text-primary" aria-hidden="true" />
              <div>
                <span className="text-xs font-bold text-text block">Source Course PDF</span>
                <span className="text-[11px] text-text-muted">
                  {document.hasOcrPages ? 'OCR-processed PDF' : 'Native digital PDF text'}
                </span>
              </div>
            </div>

            <a
              href={`/api/v1/documents/${document.documentId}/file`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-sm border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text hover:bg-surface-subtle hover:border-primary/50 transition-colors"
            >
              <span>View Raw PDF</span>
              <ArrowSquareOut className="size-3.5" aria-hidden="true" />
            </a>
          </div>

          {/* Technical Metadata */}
          <div className="space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-text block">
              Module Metadata
            </span>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-sm border border-border bg-surface p-3 space-y-0.5">
                <span className="text-[10px] uppercase font-semibold text-text-muted block">Course Title</span>
                <span className="font-semibold text-text">{document.courseTitle || '—'}</span>
              </div>
              <div className="rounded-sm border border-border bg-surface p-3 space-y-0.5">
                <span className="text-[10px] uppercase font-semibold text-text-muted block">Lesson / Unit</span>
                <span className="font-semibold text-text">{document.lessonTitle || '—'}</span>
              </div>
              <div className="rounded-sm border border-border bg-surface p-3 space-y-0.5">
                <span className="text-[10px] uppercase font-semibold text-text-muted block">Academic Year</span>
                <span className="font-semibold text-text">{document.academicYear || '—'}</span>
              </div>
              <div className="rounded-sm border border-border bg-surface p-3 space-y-0.5">
                <span className="text-[10px] uppercase font-semibold text-text-muted block">Uploaded</span>
                <span className="font-semibold text-text tabular-nums">{new Date(document.uploadedAt).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          {/* Extracted Outline */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-text block">
                Detected Module Outline
              </span>
              <span className="text-[11px] text-text-muted">
                {outline.length > 0 ? `${outline.length} sections` : 'No sections detected'}
              </span>
            </div>

            {outline.length > 0 ? (
              <div className="rounded-md border border-border bg-surface divide-y divide-border overflow-hidden text-xs">
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
            ) : (
              <div className="rounded-sm border border-border bg-surface-subtle p-4 text-xs text-text-muted text-center">
                Outline extraction completed. Content is indexed into {document.chunks?.length ?? 0} semantic chunks.
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
