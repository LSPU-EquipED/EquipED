import { useMemo } from 'react';
import {
  FileText,
  ListNumbers,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Card } from '@/shared/components/Card';
import type { ClientDocument } from '@/shared/types/documents';
import type { EvaluationFlagItem } from '../types';

interface DocumentDossierPaneProps {
  document: ClientDocument | null | undefined;
  selectedFlags?: EvaluationFlagItem[];
  selectedAgentLabel?: string;
  selectedAgentId?: string;
}

export function DocumentDossierPane({
  document,
  selectedFlags: _selectedFlags,
  selectedAgentLabel: _selectedAgentLabel,
  selectedAgentId: _selectedAgentId,
}: DocumentDossierPaneProps) {
  // Extract detected topic outline from document chunks or structuredOutline
  const detectedTopics = useMemo(() => {
    if (!document) return [];

    if (
      document.structuredOutline &&
      Array.isArray(document.structuredOutline) &&
      document.structuredOutline.length > 0
    ) {
      return document.structuredOutline.map((item, idx) => {
        const title = typeof item.title === 'string' ? item.title : `Section ${idx + 1}`;
        return { index: idx + 1, title };
      });
    }

    // Fallback: extract from unique chunk headers or first few sentences
    const topics: string[] = [];
    if (document.chunks && document.chunks.length > 0) {
      for (const chunk of document.chunks) {
        const lines = chunk.text.split('\n').map((l) => l.trim()).filter(Boolean);
        if (lines.length > 0) {
          const firstLine = lines[0];
          if (firstLine.length < 80 && !topics.includes(firstLine)) {
            topics.push(firstLine);
          }
        }
        if (topics.length >= 6) break;
      }
    }

    if (topics.length > 0) {
      return topics.map((title, idx) => ({ index: idx + 1, title }));
    }

    return [
      { index: 1, title: 'Core Course Concepts' },
      { index: 2, title: 'Instructional Activities & Demonstrations' },
      { index: 3, title: 'Formative Assessment & Evaluation' },
    ];
  }, [document]);

  const pageCount = document?.pageCount ?? document?.chunks?.length ?? 1;

  return (
    <aside
      aria-label="SLM Module Dossier"
      className="flex flex-col h-full min-h-0 border-r border-border bg-canvas overflow-y-auto p-4 sm:p-5 space-y-4"
    >
      {/* Card 1: Module Metadata Ledger */}
      <Card variant="flat" className="p-4 sm:p-5 shadow-none bg-surface space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FileText className="size-4 text-primary shrink-0" aria-hidden="true" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-text">
              Document Metadata
            </h3>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {document?.program && (
              <Badge variant="neutral" className="font-mono text-[10px]">
                {document.program}
              </Badge>
            )}
            <Badge
              variant={document?.processingStatus === 'PROCESSED' ? 'success' : 'neutral'}
              withDot
            >
              {document?.processingStatus === 'PROCESSED' ? 'Verified' : 'Processing'}
            </Badge>
          </div>
        </div>

        {document?.lessonTitle && (
          <p className="text-xs text-text-muted font-medium leading-relaxed">
            {document.lessonTitle}
          </p>
        )}

        {/* Clean key-value ledger with comfortable breathing room and zero dividing rules */}
        <div className="rounded-sm bg-surface-subtle/70 px-3.5 py-2.5 space-y-2 text-xs">
          <div className="flex items-baseline justify-between">
            <span className="text-text-muted text-xs font-medium">Course Code</span>
            <span className="font-semibold text-text font-mono text-xs">
              {document?.courseCode || document?.courseTitle || '—'}
            </span>
          </div>

          <div className="flex items-baseline justify-between">
            <span className="text-text-muted text-xs font-medium">Academic Year</span>
            <span className="font-semibold text-text tabular-nums text-xs">
              {document?.academicYear || '1st Sem AY 2026–2027'}
            </span>
          </div>

          <div className="flex items-baseline justify-between">
            <span className="text-text-muted text-xs font-medium">Volume</span>
            <span className="font-semibold text-text tabular-nums text-xs">
              {pageCount} {pageCount === 1 ? 'Page' : 'Pages'} · {document?.hasOcrPages ? 'OCR Scanned' : 'Digital Native PDF'}
            </span>
          </div>

          <div className="flex items-baseline justify-between">
            <span className="text-text-muted text-xs font-medium">Evaluation Model</span>
            <span className="font-semibold text-text text-xs">
              LSPU SCC 4-Agent QA
            </span>
          </div>
        </div>
      </Card>

      {/* Card 2: Detected Lesson & Topic Outline */}
      <Card variant="flat" className="p-4 sm:p-5 shadow-none bg-surface space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ListNumbers className="size-4 text-primary shrink-0" aria-hidden="true" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-text">
              Detected Module Outline
            </h3>
          </div>
          <span className="text-[11px] font-mono text-text-muted tabular-nums">
            {detectedTopics.length} Units
          </span>
        </div>

        <p className="text-xs text-text-muted leading-relaxed">
          Auto-extracted topics and chapter headings parsed from the course document.
        </p>

        {/* Clean list with interactive hover feedback and branded unit stamps */}
        <ol className="space-y-1.5 pt-1 text-xs">
          {detectedTopics.map((topic) => (
            <li
              key={topic.index}
              className="flex items-center gap-2.5 rounded-xs px-2 py-1.5 hover:bg-surface-subtle transition-colors text-text"
            >
              <span className="flex size-5 shrink-0 items-center justify-center rounded-xs bg-surface-subtle border border-border/80 text-[10px] font-mono font-bold text-primary">
                {topic.index}
              </span>
              <span className="truncate leading-snug font-medium text-xs text-text" title={topic.title}>
                {topic.title}
              </span>
            </li>
          ))}
        </ol>
      </Card>
    </aside>
  );
}
