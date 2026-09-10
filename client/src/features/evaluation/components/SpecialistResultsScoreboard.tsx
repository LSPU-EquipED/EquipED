import { CheckCircle, NotePencil, Play } from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import type { ClientDocument } from '@/shared/types/documents';
import type { TargetAgent, TargetAgentMeta } from '@/shared/types/evaluations';
import type { DeskQueueItem, DomainScoreBlock, EvaluationResultsResponse } from '../types';
import { SpecialistExportDownloadButton } from './ExportDocument';
import {
  cleanJustification,
  formatScore,
  monitoringPercentage,
} from '../utils/scoreHelpers';

const ADJECTIVAL_RATING_CLASSES: Record<string, string> = {
  'Very Satisfactory': 'bg-success-soft text-success border-success/30',
  'Satisfactory': 'bg-info-soft text-info border-info/30',
  'Needs Improvement': 'bg-warning-soft text-warning border-warning/30',
  'Poor': 'bg-destructive-soft text-destructive border-destructive/30',
};

function formatUploadDate(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return '—';
  }
}

export interface SpecialistResultsScoreboardProps {
  validAgent: TargetAgent;
  meta: TargetAgentMeta;
  activeItem: DeskQueueItem | null;
  activeDocument: ClientDocument | null;
  latestJobId: string | undefined;
  results: EvaluationResultsResponse;
  domainScore: DomainScoreBlock | undefined;
  onOpenReviewModal: () => void;
  onOpenReevaluateModal: () => void;
}

export function SpecialistResultsScoreboard({
  validAgent,
  meta,
  activeItem,
  activeDocument,
  latestJobId,
  results,
  domainScore,
  onOpenReviewModal,
  onOpenReevaluateModal,
}: SpecialistResultsScoreboardProps) {
  const criteria = domainScore?.criteria ?? [];

  return (
    <div className="rounded-md border border-border bg-surface p-6 sm:p-8 space-y-6">
      {/* Row 1: Header Bar & Action Toolbar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant="info">{meta.shortLabel} Specialist Desk</Badge>
            <Badge variant="success">Completed</Badge>
          </div>
          <h2
            className="text-xl font-bold tracking-tight text-text truncate max-w-xl"
            title={activeItem?.title || activeDocument?.title || 'Course Module'}
          >
            {activeItem?.title || activeDocument?.title || 'Course Module'}
          </h2>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted font-mono">
            <span>{activeItem?.course_code || activeDocument?.courseCode || 'General'}</span>
            <span>•</span>
            <span>{activeItem?.program || activeDocument?.program || 'BSCS'}</span>
            <span>•</span>
            <span>Uploaded {formatUploadDate(activeItem?.uploaded_at || activeDocument?.uploadedAt)}</span>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onOpenReviewModal}
            className="font-semibold text-xs gap-1.5 h-8.5 px-3 whitespace-nowrap"
          >
            <NotePencil className="size-3.5" aria-hidden="true" />
            <span>Review & Correct Scores</span>
          </Button>

          {domainScore && (
            <SpecialistExportDownloadButton
              domainData={{
                agentId: validAgent,
                documentTitle: results.document_title || activeItem?.title || activeDocument?.title || 'Course Module',
                program: results.program || activeItem?.program || activeDocument?.program || null,
                courseCode: activeItem?.course_code || activeDocument?.courseCode || null,
                evaluationId: latestJobId || '',
                criteria,
                subtotal: domainScore.subtotal,
                max_score: domainScore.max_score || 4,
                status: domainScore.status || results.evaluation_status || 'COMPLETED',
                adjectival_rating: domainScore.adjectival_rating ?? undefined,
                summary: domainScore.summary,
                version: domainScore.version,
                form_snapshot_id: domainScore.form_snapshot_id ?? undefined,
                results,
                document: activeDocument ?? null,
              }}
              agentId={validAgent}
              variant="secondary"
            />
          )}

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onOpenReevaluateModal}
            className="font-semibold text-xs gap-1.5 h-8.5 px-3 whitespace-nowrap"
          >
            <Play className="size-3.5 fill-current" weight="fill" aria-hidden="true" />
            <span>Re-evaluate</span>
          </Button>
        </div>
      </div>

      {/* Row 2: Executive Metrics Dashboard Strip */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center rounded-sm border border-border bg-surface-subtle p-5">
        <div className="md:col-span-5 lg:col-span-4 space-y-2 border-b md:border-b-0 md:border-r border-border pb-4 md:pb-0 md:pr-6">
          <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted block">
            {meta.fullName} Performance Score
          </h3>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-text tabular-nums tracking-tight">
              {formatScore(domainScore?.subtotal ?? 0)}
            </span>
            <span className="text-sm font-semibold text-text-muted tabular-nums">
              / {formatScore(domainScore?.max_score || 4)}
            </span>
            {domainScore?.adjectival_rating && (
              <span
                className={cn(
                  'ml-2 inline-flex items-center rounded-xs px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider border',
                  ADJECTIVAL_RATING_CLASSES[domainScore.adjectival_rating] ||
                    'bg-surface text-text-muted border-border',
                )}
              >
                {domainScore.adjectival_rating}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2.5 pt-0.5">
            <div className="w-28 h-1.5 rounded-full bg-border overflow-hidden">
              <div
                className="h-full bg-primary rounded-full"
                style={{
                  width: `${Math.min(100, Math.max(0, monitoringPercentage(domainScore?.subtotal ?? 0, domainScore?.max_score || 4)))}%`,
                }}
              />
            </div>
            <span className="text-xs text-text-muted tabular-nums font-semibold">
              {monitoringPercentage(domainScore?.subtotal ?? 0, domainScore?.max_score || 4)}% Compliance
            </span>
          </div>
        </div>

        <div className="md:col-span-7 lg:col-span-8 space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted block">
            Specialist Executive Summary
          </span>
          <p className="text-xs text-text-muted leading-relaxed">
            {domainScore?.summary || meta.requirement}
          </p>
        </div>
      </div>

      {/* Row 3: Criteria Breakdown Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-text">
            Criteria Breakdown ({criteria.length} Criteria)
          </h3>
          <span className="text-[11px] text-text-muted tabular-nums">
            {results.completed_at
              ? `Completed: ${new Date(results.completed_at).toLocaleDateString()}`
              : results.submitted_at
              ? `Submitted: ${new Date(results.submitted_at).toLocaleDateString()}`
              : ''}
          </span>
        </div>

        <div className="overflow-x-auto rounded-md border border-border bg-surface shadow-none">
          <table className="w-full text-left border-collapse text-xs">
            <thead className="bg-surface-subtle border-b border-border text-[11px] font-bold uppercase tracking-wider text-text-muted">
              <tr>
                <th scope="col" className="p-3 w-20">Code</th>
                <th scope="col" className="p-3">Criterion</th>
                <th scope="col" className="p-3 w-28 text-center">Score (/4)</th>
                <th scope="col" className="p-3 min-w-[18rem]">Justification & Grounded Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-surface">
              {criteria.map((criterion, idx) => {
                const isPassing = criterion.score >= 3.0;
                return (
                  <tr
                    key={criterion.criterion_id || idx}
                    className="hover:bg-surface-subtle/30 transition-colors"
                  >
                    <td className="p-3.5 align-top font-mono font-bold text-xs text-primary whitespace-nowrap">
                      <span className="bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-xs">
                        {criterion.criterion_id}
                      </span>
                    </td>
                    <td className="p-3.5 align-top">
                      <span className="font-semibold text-text block leading-snug">
                        {criterion.criterion_text}
                      </span>
                      {criterion.description ? (
                        <p className="text-text-muted mt-1 leading-relaxed text-[11px]">
                          {criterion.description}
                        </p>
                      ) : null}
                    </td>
                    <td className="p-3.5 align-top text-center">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-xs px-2.5 py-0.5 font-bold tabular-nums border text-xs',
                          isPassing
                            ? 'bg-success-soft text-success border-success/30'
                            : 'bg-warning-soft text-warning border-warning/30',
                        )}
                      >
                        {formatScore(criterion.score)} / 4
                      </span>
                    </td>
                    <td className="p-3.5 align-top space-y-2">
                      {criterion.evidence ? (
                        <div className="rounded-sm border border-border bg-surface-subtle p-2.5 space-y-1">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                            SLM Quoted Evidence
                          </span>
                          <blockquote className="border-l-2 border-primary/40 pl-2.5 font-mono text-[11px] text-text leading-relaxed italic">
                            &ldquo;{cleanJustification(criterion.evidence)}&rdquo;
                          </blockquote>
                        </div>
                      ) : null}

                      {criterion.justification ? (
                        <p className="text-text-muted leading-relaxed text-xs">
                          <strong className="text-text font-semibold">Specialist Finding: </strong>
                          {cleanJustification(criterion.justification)}
                        </p>
                      ) : !criterion.evidence ? (
                        <span className="text-success text-xs flex items-center gap-1.5 font-medium">
                          <CheckCircle className="size-3.5 text-success shrink-0" aria-hidden="true" />
                          Verified compliant with quality standards.
                        </span>
                      ) : null}

                      {criterion.reviewer_correction ? (
                        <div className="rounded-sm border border-info/30 bg-info-soft/20 p-2.5 text-xs space-y-1">
                          <span className="font-bold text-info block text-[10px] uppercase">
                            Authoritative CID Human Override Applied
                          </span>
                          {criterion.reviewer_correction.score != null ? (
                            <p className="text-text font-medium">
                              Override Score: {formatScore(criterion.reviewer_correction.score)} / 4
                            </p>
                          ) : null}
                          {criterion.reviewer_correction.justification ? (
                            <p className="text-text-muted leading-relaxed">
                              <strong>Reviewer Justification: </strong>
                              {cleanJustification(criterion.reviewer_correction.justification)}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
