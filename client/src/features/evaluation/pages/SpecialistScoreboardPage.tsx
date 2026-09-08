import { useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate, Link } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  BookOpen,
  CheckCircle,
  Circle,
  Clock,
  DownloadSimple,
  FileText,
  FolderOpen,
  GraduationCap,
  Lightbulb,
  ListChecks,
  Play,
  ShieldCheck,
  Spinner,
  WarningCircle,
} from '@phosphor-icons/react';
import { documentsApi } from '@/shared/api/documents.api';
import { evaluationApi } from '../api/evaluation.api';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES } from '@/shared/constants/theme';
import {
  isTargetAgent,
  TARGET_AGENT_META,
  type TargetAgent,
} from '@/shared/types/evaluations';
import type { ClientDocument } from '@/shared/types/documents';
import {
  formatScore,
  cleanJustification,
  monitoringPercentage,
} from '../utils/scoreHelpers';
import { EvaluationConfirmModal } from '../components/EvaluationConfirmModal';
import { GadExportDownloadButton } from '../components/ExportDocument';

const ROLE_ICONS: Record<TargetAgent, typeof GraduationCap> = {
  sme: GraduationCap,
  coordinator: ListChecks,
  gad: ShieldCheck,
  itso: Lightbulb,
};

export interface SpecialistScoreboardPageProps {
  agentId?: TargetAgent;
  documentId?: string;
}

export function SpecialistScoreboardPage({
  agentId: propAgentId,
  documentId: propDocId,
}: SpecialistScoreboardPageProps = {}) {
  const params = useParams({ strict: false }) as {
    agentId?: string;
    documentId?: string;
  };
  const resolvedAgent = propAgentId ?? params.agentId;
  const validAgent: TargetAgent = isTargetAgent(resolvedAgent) ? resolvedAgent : 'sme';
  const meta = TARGET_AGENT_META[validAgent];
  const Icon = ROLE_ICONS[validAgent] || GraduationCap;
  const routeDocId = propDocId ?? params.documentId;
  const navigate = useNavigate();

  const [selectedDocId, setSelectedDocId] = useState<string | null>(routeDocId ?? null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  // 1. Fetch available processed SLMs from Storage
  const { data: docsData, isLoading: isLoadingDocs } = useQuery({
    queryKey: ['storage-slm-documents'],
    queryFn: () => documentsApi.listDocuments({ sourceType: 'slm', page: 1, pageSize: 100 }),
    staleTime: 30000,
  });

  const slmDocuments: ClientDocument[] = useMemo(() => {
    return (docsData?.items ?? []).filter((d: ClientDocument) => d.processingStatus === 'PROCESSED');
  }, [docsData]);
  // Default to first document if none selected
  const activeDocument = useMemo(() => {
    if (selectedDocId) {
      return slmDocuments.find((d) => d.documentId === selectedDocId) ?? null;
    }
    return slmDocuments[0] ?? null;
  }, [slmDocuments, selectedDocId]);

  const activeDocId = activeDocument?.documentId;

  // 2. Resolve the latest evaluation job for this SLM and this specialist role
  const { data: evalsData, isLoading: isLoadingEvals, refetch: refetchEvals } = useQuery({
    queryKey: ['specialist-evaluations', activeDocId, validAgent],
    queryFn: () => evaluationApi.listEvaluations(activeDocId),
    enabled: Boolean(activeDocId),
    staleTime: 10000,
  });

  const latestJob = evalsData?.items?.[0];
  const isEvaluating =
    latestJob?.status === 'SUBMITTED' ||
    latestJob?.status === 'PREPROCESSING' ||
    latestJob?.status === 'EVALUATING' ||
    latestJob?.status === 'SYNTHESIZING';

  // 3. If a completed or terminal job exists, fetch results
  const evaluationId = latestJob?.evaluation_id;
  const { data: results, isLoading: isLoadingResults, refetch: refetchResults } = useQuery({
    queryKey: ['specialist-results', evaluationId],
    queryFn: () => evaluationApi.getEvaluationResults(evaluationId!),
    enabled: Boolean(evaluationId && latestJob?.status === 'COMPLETED'),
    staleTime: 15000,
  });

  const domainScore = results?.domain_scores?.[validAgent];
  const criteria = useMemo(() => {
    return (domainScore?.criteria || []).slice().sort((a, b) => {
      if (a.display_order != null && b.display_order != null) {
        return a.display_order - b.display_order;
      }
      return a.criterion_id.localeCompare(b.criterion_id, undefined, { numeric: true });
    });
  }, [domainScore]);

  const handleDocumentChange = (docId: string) => {
    setSelectedDocId(docId);
    void navigate({
      to: '/specialists/$agentId/$documentId',
      params: { agentId: validAgent, documentId: docId },
    });
  };

  const handleModalSubmitted = useCallback(() => {
    void refetchEvals();
    void refetchResults();
  }, [refetchEvals, refetchResults]);

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)] bg-canvas">
      {/* ── Top Role Banner & SLM Context ────────────────────────────────── */}
      <header className="border-b border-border bg-surface px-6 py-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="flex size-10 items-center justify-center rounded-sm bg-primary/10 text-primary shrink-0 border border-primary/20">
              <Icon className="size-5" aria-hidden="true" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight text-text">
                  {meta.fullName} Review
                </h1>
                <Badge variant="info">{meta.shortLabel} Specialist</Badge>
              </div>
              <p className="text-xs text-text-muted mt-0.5 max-w-xl leading-relaxed">
                {meta.requirement}
              </p>
            </div>
          </div>

          {/* SLM Document Picker */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <label
                htmlFor="slm-picker"
                className="text-xs font-semibold text-text-muted uppercase tracking-wider whitespace-nowrap"
              >
                Active SLM:
              </label>
              {isLoadingDocs ? (
                <div className="h-9 w-64 animate-pulse rounded-sm bg-surface-subtle border border-border" />
              ) : slmDocuments.length === 0 ? (
                <span className="text-xs text-text-muted">No processed SLMs in storage</span>
              ) : (
                <select
                  id="slm-picker"
                  value={activeDocId ?? ''}
                  onChange={(e) => handleDocumentChange(e.target.value)}
                  className="h-9 w-72 rounded-sm border border-border bg-surface px-3 text-xs font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
                >
                  {slmDocuments.map((doc) => (
                    <option key={doc.documentId} value={doc.documentId}>
                      {doc.courseCode ? `${doc.courseCode} — ` : ''}{doc.title}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={!activeDocument || isEvaluating}
              onClick={() => setShowConfirmModal(true)}
              className="h-9 px-4 text-xs font-bold uppercase tracking-wider gap-1.5"
            >
              {isEvaluating ? (
                <>
                  <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                  <span>Evaluating…</span>
                </>
              ) : (
                <>
                  <Play className="size-3 fill-current" weight="fill" aria-hidden="true" />
                  <span>{domainScore ? 'Re-Evaluate' : `Evaluate as ${meta.shortLabel}`}</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </header>

      {/* ── Main Specialist Workspace & Scoreboard ──────────────────────── */}
      <main className="flex-1 p-6 max-w-[108rem] w-full mx-auto space-y-6">
        {isLoadingDocs ? (
          <div className="rounded-md border border-border bg-surface p-12 text-center flex flex-col items-center justify-center space-y-3">
            <Spinner className="size-8 text-primary animate-spin" aria-hidden="true" />
            <p className="text-xs text-text-muted">Loading SLM documents from storage…</p>
          </div>
        ) : !activeDocument ? (
          <div className="rounded-md border border-border bg-surface p-12 text-center flex flex-col items-center justify-center space-y-3">
            <FolderOpen className="size-10 text-text-muted/50" aria-hidden="true" />
            <h2 className="text-base font-bold text-text">No SLMs in Storage</h2>
            <p className="text-xs text-text-muted max-w-sm">
              Upload course modules in the SLM Storage repository before running specialist evaluations.
            </p>
            <Link
              to="/documents"
              className="inline-flex items-center gap-1.5 rounded-sm bg-primary px-4 py-2 text-xs font-semibold text-white hover:bg-primary/90"
            >
              <span>Go to SLM Storage</span>
            </Link>
          </div>
        ) : isEvaluating ? (
          /* Evaluating Progress State */
          <div className="rounded-md border border-info/30 bg-info-soft/30 p-10 text-center flex flex-col items-center justify-center space-y-3">
            <Spinner className="size-8 text-info animate-spin" aria-hidden="true" />
            <h2 className="text-base font-bold text-text">
              {meta.fullName} Evaluation in Progress
            </h2>
            <p className="text-xs text-text-muted max-w-md">
              Analyzing module content against the institutional {meta.shortLabel} rubric. Results typically arrive within 20–30 seconds.
            </p>
          </div>
        ) : !domainScore ? (
          /* Unevaluated State */
          <div className="rounded-md border border-dashed border-border bg-surface p-12 text-center flex flex-col items-center justify-center space-y-4">
            <div className="flex size-12 items-center justify-center rounded-sm bg-surface-subtle border border-border text-text-muted">
              <Icon className="size-6" aria-hidden="true" />
            </div>
            <div className="space-y-1 max-w-md">
              <h2 className="text-base font-bold text-text">
                No {meta.fullName} Evaluation Yet
              </h2>
              <p className="text-xs text-text-muted leading-relaxed">
                This SLM (<span className="font-semibold text-text">{activeDocument.title}</span>) has not been evaluated by the {meta.shortLabel} specialist.
              </p>
            </div>
            <Button
              type="button"
              variant="primary"
              size="md"
              onClick={() => setShowConfirmModal(true)}
              className="font-bold uppercase tracking-wider text-xs gap-2"
            >
              <Play className="size-3.5 fill-current" weight="fill" aria-hidden="true" />
              <span>Launch {meta.shortLabel} Evaluation (~20-30s)</span>
            </Button>
          </div>
        ) : (
          /* Dedicated Specialist Scoreboard */
          <div className="space-y-6">
            {/* Top Score Summary Card */}
            <div className="rounded-md border border-border bg-surface p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
                  {meta.fullName} Performance Score
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-text tabular-nums">
                    {formatScore(domainScore.subtotal)} / {formatScore(domainScore.max_score || 4)}
                  </span>
                  {domainScore.adjectival_rating && (
                    <Badge variant="info">
                      {domainScore.adjectival_rating}
                    </Badge>
                  )}
                  <span className="text-xs font-semibold text-text-muted tabular-nums">
                    ({monitoringPercentage(domainScore.subtotal, domainScore.max_score || 4)}% Accreditation)
                  </span>
                </div>
                {domainScore.summary && (
                  <p className="text-xs text-text-muted mt-1 leading-relaxed max-w-2xl">
                    {domainScore.summary}
                  </p>
                )}
              </div>

              {/* Specialist Utilities (e.g. GAD Form Export) */}
              <div className="flex items-center gap-2 shrink-0">
                {validAgent === 'gad' && results && (
                  <GadExportDownloadButton
                    domainData={{
                      agentId: 'gad',
                      documentTitle: activeDocument.title,
                      program: activeDocument.program ?? null,
                      courseTitle: activeDocument.courseTitle ?? null,
                      courseCode: activeDocument.courseCode ?? null,
                      academicYear: activeDocument.academicYear ?? null,
                      reviewer: null,
                      evaluationId: latestJob?.evaluation_id,
                      isPartial: false,
                      partialReason: null,
                      evaluationStatus: results.evaluation_status,
                      subtotal: domainScore.subtotal,
                      max_score: domainScore.max_score || 4,
                      status: domainScore.status,
                      adjectival_rating: domainScore.adjectival_rating ?? undefined,
                      criteria: domainScore.criteria || [],
                      summary: domainScore.summary,
                      version: domainScore.version,
                      form_snapshot_id: domainScore.form_snapshot_id,
                      results,
                      document: activeDocument,
                    }}
                  />
                )}
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowConfirmModal(true)}
                  className="h-8 px-3 text-xs font-semibold"
                >
                  <span>Re-evaluate</span>
                </Button>
              </div>
            </div>

            {/* Criteria Breakdown Table */}
            <div className="rounded-md border border-border bg-surface overflow-hidden">
              <div className="border-b border-border bg-surface-subtle px-5 py-3 flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-text">
                  Criterion Breakdown ({criteria.length} Criteria)
                </span>
                <span className="text-[11px] font-mono text-text-muted">
                  Form Rev {domainScore.version ?? '1'}
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className={TABLE_STYLES.table}>
                  <thead className={TABLE_STYLES.thead}>
                    <tr>
                      <th scope="col" className={cn(TABLE_STYLES.th, 'w-24')}>Code</th>
                      <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[14rem]')}>Criterion</th>
                      <th scope="col" className={cn(TABLE_STYLES.th, 'w-24 text-center')}>Score</th>
                      <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[18rem]')}>Justification & Grounded Evidence</th>
                    </tr>
                  </thead>
                  <tbody className={TABLE_STYLES.tbody}>
                    {criteria.map((crit) => {
                      const scoreNum = crit.score;
                      const hasEvidence = Boolean(crit.evidence);

                      return (
                        <tr key={crit.criterion_id} className={TABLE_STYLES.tr}>
                          <td className={cn(TABLE_STYLES.td, 'font-mono text-xs font-bold text-primary')}>
                            {crit.criterion_id}
                          </td>
                          <td className={TABLE_STYLES.td}>
                            <div className="space-y-0.5">
                              <span className="text-xs font-bold text-text block">
                                {crit.criterion_text}
                              </span>
                              {crit.description && (
                                <p className="text-[11px] text-text-muted leading-relaxed">
                                  {crit.description}
                                </p>
                              )}
                            </div>
                          </td>
                          <td className={cn(TABLE_STYLES.td, 'text-center')}>
                            <span className={cn(
                              'inline-flex items-center justify-center font-mono text-xs font-bold px-2 py-0.5 rounded-xs border',
                              scoreNum >= 3
                                ? 'bg-success-soft text-success border-success/30'
                                : scoreNum >= 2
                                  ? 'bg-warning-soft text-warning border-warning/30'
                                  : 'bg-destructive-soft text-destructive border-destructive/30'
                            )}>
                              {scoreNum} / 4
                            </span>
                          </td>
                          <td className={TABLE_STYLES.td}>
                            <div className="space-y-1.5 text-xs">
                              {crit.justification && (
                                <p className="text-text leading-relaxed">
                                  {cleanJustification(crit.justification)}
                                </p>
                              )}
                              {hasEvidence && (
                                <div className="rounded-xs border border-border bg-surface-subtle p-2 text-[11px] text-text-muted font-mono leading-relaxed">
                                  <span className="font-bold text-text-muted block text-[10px] uppercase">
                                    Quoted SLM Evidence:
                                  </span>
                                  &ldquo;{crit.evidence}&rdquo;
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Confirmation Modal ───────────────────────────────────────────── */}
      {showConfirmModal && activeDocument && (
        <EvaluationConfirmModal
          documentId={activeDocument.documentId}
          documentTitle={activeDocument.title}
          detectedProgram={activeDocument.program}
          targetAgent={validAgent}
          onClose={() => setShowConfirmModal(false)}
          onSubmitted={handleModalSubmitted}
        />
      )}
    </div>
  );
}
export default SpecialistScoreboardPage;
