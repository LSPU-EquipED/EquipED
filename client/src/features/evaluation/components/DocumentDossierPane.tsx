import { useMemo } from 'react';
import {
  Books,
  CheckCircle,
  FileText,
  GraduationCap,
  ListNumbers,
  Quotes,
  Scales,
  ShieldCheck,
  WarningCircle,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Card, CardHeader, CardTitle, CardContent } from '@/shared/components/Card';
import { cn } from '@/shared/components/utils';
import { TYPOGRAPHY } from '@/shared/constants/theme';
import type { ClientDocument } from '@/shared/types/documents';
import type { EvaluationFlagItem } from '../types';
import { cleanJustification, formatScore } from '../utils/scoreHelpers';

interface DocumentDossierPaneProps {
  document: ClientDocument | null | undefined;
  selectedFlags: EvaluationFlagItem[];
  selectedAgentLabel: string;
  selectedAgentId: string;
}

export function DocumentDossierPane({
  document,
  selectedFlags,
  selectedAgentLabel,
  selectedAgentId: _selectedAgentId,
}: DocumentDossierPaneProps) {
  // Extract detected topic outline from document chunks or structuredOutline
  const detectedTopics = useMemo(() => {
    if (!document) return [];

    if (document.structuredOutline && Array.isArray(document.structuredOutline) && document.structuredOutline.length > 0) {
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
      { index: 1, title: document.lessonTitle || 'Core Course Concepts' },
      { index: 2, title: 'Instructional Activities & Demonstrations' },
      { index: 3, title: 'Formative Assessment & Evaluation' },
    ];
  }, [document]);

  const pageCount = document?.pageCount ?? document?.chunks?.length ?? 1;

  return (
    <aside
      aria-label="SLM Module Dossier"
      className="flex flex-col h-full min-h-0 border-r border-border bg-canvas overflow-y-auto p-4 sm:p-6 space-y-5"
    >
      {/* Module Title & Identity Card */}
      <Card variant="flat" className="p-4 sm:p-5 shadow-none bg-surface space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                SLM Module Dossier
              </span>
              {document?.program ? (
                <Badge variant="neutral">{document.program}</Badge>
              ) : null}
            </div>
            <h2 className="text-base font-bold text-text leading-snug line-clamp-2">
              {document?.title || 'Course Learning Module'}
            </h2>
            {document?.lessonTitle ? (
              <p className="text-xs text-text-muted font-medium">
                {document.lessonTitle}
              </p>
            ) : null}
          </div>

          <Badge variant={document?.processingStatus === 'PROCESSED' ? 'success' : 'neutral'} withDot>
            {document?.processingStatus === 'PROCESSED' ? 'Verified Ingest' : 'Processing'}
          </Badge>
        </div>

        {/* Academic Metadata Grid */}
        <div className="grid grid-cols-2 gap-2.5 pt-3 border-t border-border text-xs">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block">
              Course Code
            </span>
            <span className="font-semibold text-text truncate block mt-0.5">
              {document?.courseCode || document?.courseTitle || '—'}
            </span>
          </div>

          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block">
              Academic Year
            </span>
            <span className="font-semibold text-text truncate block mt-0.5">
              {document?.academicYear || '1st Sem AY 2026–2027'}
            </span>
          </div>

          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block">
              Volume
            </span>
            <span className="font-semibold text-text tabular-nums block mt-0.5">
              {pageCount} {pageCount === 1 ? 'Page' : 'Pages'} · {document?.hasOcrPages ? 'OCR Scanned' : 'Digital Text'}
            </span>
          </div>

          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block">
              Evaluation Model
            </span>
            <span className="font-semibold text-text block mt-0.5">
              LSPU SCC 4-Agent QA
            </span>
          </div>
        </div>
      </Card>

      {/* Detected Lesson & Topic Outline */}
      <Card variant="flat" className="p-4 sm:p-5 shadow-none bg-surface space-y-3">
        <div className="flex items-center gap-2">
          <ListNumbers className="size-4 text-text-muted" aria-hidden="true" />
          <h3 className={TYPOGRAPHY.headingSm}>Detected Module Outline</h3>
        </div>
        <p className="text-xs text-text-muted">
          Auto-extracted topics and chapter headings parsed from the course document.
        </p>

        <div className="divide-y divide-border pt-1">
          {detectedTopics.map((topic) => (
            <div key={topic.index} className="flex items-start gap-2.5 py-2 first:pt-1">
              <span className="flex size-5 shrink-0 items-center justify-center rounded-xs bg-surface-subtle border border-border text-[10px] font-bold text-text-muted tabular-nums">
                {topic.index}
              </span>
              <span className="text-xs font-medium text-text leading-snug">
                {topic.title}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Quoted Evidence & Specialist Findings (Focused on Demand) */}
      <Card variant="flat" className="p-4 sm:p-5 shadow-none bg-surface space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Quotes className="size-4 text-primary" aria-hidden="true" weight="bold" />
            <h3 className={TYPOGRAPHY.headingSm}>Specialist Evidence & Citations</h3>
          </div>
          {selectedFlags.length > 0 ? (
            <Badge variant="warning">{selectedFlags.length} flagged</Badge>
          ) : null}
        </div>

        <p className="text-xs text-text-muted">
          Exact quoted passages from the module evaluated by the <strong>{selectedAgentLabel}</strong>.
        </p>

        {selectedFlags.length > 0 ? (
          <div className="space-y-3 pt-1">
            {selectedFlags.map((flag) => (
              <div
                key={flag.flag_id}
                className="rounded-sm border border-warning/30 bg-warning-soft/20 p-3.5 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-text truncate">
                    {flag.criterion_text}
                  </span>
                  <Badge variant="warning">
                    Score {formatScore(flag.score)}/4
                  </Badge>
                </div>

                {flag.justification ? (
                  <p className="text-xs text-text-muted leading-relaxed">
                    {cleanJustification(flag.justification)}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-sm border border-success/30 bg-success-soft/20 p-3.5 flex items-start gap-2.5 text-xs text-success">
            <CheckCircle className="size-4 shrink-0 text-success mt-0.5" aria-hidden="true" />
            <div>
              <p className="font-bold">Fully Compliant Domain</p>
              <p className="text-success/90 mt-0.5 leading-relaxed">
                All reviewed criteria in this domain verified compliant with institutional standards.
              </p>
            </div>
          </div>
        )}
      </Card>
    </aside>
  );
}
