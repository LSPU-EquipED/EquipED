import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Lightbulb,
  Scale,
  ShieldCheck,
  Target,
} from 'lucide-react';
import { useEffect, useMemo, useState, type PointerEvent } from 'react';
import { useParams } from '@tanstack/react-router';
import { documentsApi } from '@/shared/api/documents.api';
import { getErrorMessage } from '@/shared/api/http';
import { Button } from '@/shared/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/shared/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { cn } from '@/shared/components/utils';
import { useFetch } from '@/shared/hooks/useFetch';
import type { ClientDocument, ClientDocumentChunk } from '@/shared/types/documents';
import { EvaluationStatusBanner } from './EvaluationStatusBanner';
import { FeedbackPanel } from './FeedbackPanel';
import { FlagList } from './FlagList';
import {
  GadExportDownloadButton,
  GadExportPreview,
  type ExportAgentId,
  type ExportDomainData,
} from './ExportDocument';

import { useQuery } from '@tanstack/react-query';
import { evaluationApi } from '@/features/evaluation/api/evaluation.api';
import { useSubmitEvaluation } from '@/features/upload/hooks/useSubmitEvaluation';
import type { CriterionScoreItem } from '../types';

const agents = [
  {
    id: 'coordinator',
    name: 'Program Coordinator',
    subtitle: 'Curriculum alignment',
    icon: BookOpen,
  },
  {
    id: 'sme',
    name: 'Subject Matter Expert (SME)',
    subtitle: 'Discipline accuracy',
    icon: Lightbulb,
  },
  {
    id: 'gad',
    name: 'GAD Unit',
    subtitle: 'Gender and development review',
    icon: Scale,
  },
  {
    id: 'itso',
    name: 'ITSO',
    subtitle: 'Innovation and compliance',
    icon: ShieldCheck,
  },
] as const;

type AgentId = ExportAgentId;
type DocumentTextGroup = {
  documentId: string;
  chunks: ClientDocumentChunk[];
};

type AgentScoreRow = {
  rating: string;
  criterion: string;
  status: string;
};

function buildDocumentTextGroups(document: ClientDocument | null): DocumentTextGroup[] {
  if (!document) {
    return [];
  }

  const groups = new Map<string, ClientDocumentChunk[]>();

  for (const chunk of document.chunks) {
    const chunks = groups.get(chunk.documentId) ?? [];
    chunks.push(chunk);
    groups.set(chunk.documentId, chunks);
  }

  return Array.from(groups.entries())
    .sort(([leftDocumentId], [rightDocumentId]) => leftDocumentId.localeCompare(rightDocumentId))
    .map(([documentId, chunks]) => ({
      documentId,
      chunks: [...chunks].sort((left, right) => left.pageNumber - right.pageNumber),
    }));
}

const EVAL_STORAGE_PREFIX = 'equiped_eval_';

export function EvaluationInterface() {
  const { documentId } = useParams({ strict: false }) as { documentId?: string };
  const submitEvaluation = useSubmitEvaluation();
  const [selectedAgentId, setSelectedAgentId] = useState<AgentId>('itso');
  const [leftPaneSize, setLeftPaneSize] = useState(48);
  const { data: document, error, isLoading, execute } = useFetch(documentsApi.getDocument);

  const storageKey = documentId ? `${EVAL_STORAGE_PREFIX}${documentId}` : null;

  const {
    data: evaluationId,
    isLoading: isResolvingEval,
    isError: isResolveError,
    error: resolveError,
    refetch: refetchResolve,
  } = useQuery({
    queryKey: ['resolve-evaluation', documentId],
    queryFn: async () => {
      if (!documentId) throw new Error('No document ID');

      if (storageKey) {
        const stored = sessionStorage.getItem(storageKey);
        if (stored) return stored;
      }

      const list = await evaluationApi.listEvaluations(documentId);
      if (list.items.length > 0) {
        const id = list.items[0].evaluation_id;
        if (storageKey) {
          sessionStorage.setItem(storageKey, id);
        }
        return id;
      }

      const result = await submitEvaluation.mutateAsync({ document_id: documentId });
      if (storageKey) {
        sessionStorage.setItem(storageKey, result.evaluation_id);
      }
      return result.evaluation_id;
    },
    enabled: !!documentId,
    staleTime: Infinity,
    retry: false,
  });

  const {
    data: results,
    refetch: refetchResults,
    isError: isResultsError,
    error: resultsError,
  } = useQuery({
    queryKey: ['evaluation-results', evaluationId],
    queryFn: () => evaluationApi.getEvaluationResults(evaluationId!),
    enabled: !!evaluationId,
    refetchInterval: (query) => {
      const evalStatus = (query.state.data as { evaluation_status?: string } | undefined)?.evaluation_status;
      if (evalStatus === 'COMPLETED' || evalStatus === 'FAILED') {
        return false;
      }
      return 3000;
    },
    retry: 1,
  });

  const { data: status } = useQuery({
    queryKey: ['evaluation-status', evaluationId],
    queryFn: () => evaluationApi.getEvaluationStatus(evaluationId!),
    enabled: !!evaluationId,
    refetchInterval: (query) => {
      const nextStatus = query.state.data?.status;
      if (nextStatus === 'COMPLETED' || nextStatus === 'FAILED') {
        return false;
      }

      return 3000;
    },
  });

  useEffect(() => {
    if (status?.status === 'COMPLETED' || status?.status === 'FAILED') {
      void refetchResults();
    }
  }, [status?.status, refetchResults]);

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];

  const isTerminal = status?.status === 'COMPLETED' || status?.status === 'FAILED';
  const hasResults = results && Object.keys(results.domain_scores).length > 0;
  const isInProgress = !!evaluationId && !isTerminal;
  const isFailedWithResults = status?.status === 'FAILED' && hasResults;

  const domainScore = results?.domain_scores[selectedAgent.id];
  const criteriaRows: AgentScoreRow[] = (domainScore?.criteria ?? []).map((criterion: CriterionScoreItem) => ({
    rating: String(criterion.score),
    criterion: criterion.criterion_text,
    status: criterion.justification || 'Evaluated',
  }));
  const selectedScore = {
    score: domainScore ? Math.round((domainScore.subtotal / (domainScore.max_score || 1)) * 100) : 0,
    rawScore: domainScore?.subtotal ?? 0,
    verdict: domainScore?.status === 'OK' ? 'Acceptable' : domainScore?.status === 'ERROR' ? 'Failed' : 'Review recommended',
    summary: domainScore
      ? `Subtotal ${domainScore.subtotal} of ${domainScore.max_score} weighted points${results?.is_partial || isFailedWithResults ? ' (partial)' : ''}.`
      : isInProgress
        ? 'Evaluation in progress...'
        : isFailedWithResults
          ? 'Evaluation failed, but partial results are available.'
          : 'Evaluation results are not available yet.',
    feedbackComments: [],
    evidenceFlags: results?.flags.filter((flag) => flag.agent_id === selectedAgent.id).map((flag) => flag.criterion_text) || [],
    rows: criteriaRows,
  };

  const domainData: ExportDomainData = {
    agentId: selectedAgent.id,
    documentTitle: document?.title || 'Unknown Document',
    program: document?.program ?? undefined,
    subtotal: domainScore?.subtotal || 0,
    max_score: domainScore?.max_score || 100,
    status: domainScore?.status || 'UNKNOWN',
    criteria: domainScore?.criteria || []
  };

  const documentTextGroups = useMemo(() => buildDocumentTextGroups(document), [document]);
  const scoreRingStyle = {
    background: `conic-gradient(var(--foreground) ${selectedScore.score * 3.6}deg, var(--muted) 0deg)`,
  };
  const documentSubtitle = [document?.courseTitle, document?.lessonTitle]
    .filter(Boolean)
    .join(' - ');

  useEffect(() => {
    if (!documentId) {
      return;
    }

    void execute(documentId).catch(() => undefined);
  }, [documentId, execute]);

  const handleDividerPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    const container = event.currentTarget.parentElement;

    if (!container) {
      return;
    }

    const bounds = container.getBoundingClientRect();

    const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
      const nextSize = ((moveEvent.clientX - bounds.left) / bounds.width) * 100;
      setLeftPaneSize(Math.min(64, Math.max(36, nextSize)));
    };

    const handlePointerUp = () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    event.currentTarget.setPointerCapture(event.pointerId);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  return (
    <section className="-mx-6 -my-7 flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-background">
      <header className="flex min-h-24 shrink-0 items-center justify-between gap-4 border-b bg-background px-10">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
            Selected Document
          </p>
          <h1 className="mt-2 truncate text-2xl font-semibold tracking-normal">
            {document?.title ?? 'Loading document...'}
          </h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button type="button" variant="outline" className="gap-2">
            <FileText className="size-4" aria-hidden="true" />
            Source
          </Button>
          <Sheet>
            <SheetTrigger asChild>
              <Button
                type="button"
                variant="outline"
                className="gap-2"
                disabled={!hasResults || !isTerminal}
              >
                <Download className="size-4" aria-hidden="true" />
                Export
              </Button>
            </SheetTrigger>
            <SheetContent className="!w-[52vw] !max-w-none gap-0 sm:!max-w-none">
              <SheetHeader className="border-b pr-14">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <SheetTitle>LSPU-CID-SF-004 {selectedAgent.name} Evaluation Export</SheetTitle>
                    <SheetDescription>
                      Preview follows the referenced Gender and Development Unit criteria form.
                    </SheetDescription>
                  </div>
                  <GadExportDownloadButton domainData={domainData} />
                </div>
              </SheetHeader>
              <div className="grid min-h-0 flex-1 place-items-start justify-items-center overflow-auto bg-muted/40 p-4 backdrop-blur-sm">
                <GadExportPreview domainData={domainData} />
              </div>
            </SheetContent>
          </Sheet>
          <Button type="button" disabled>
            Finalize Review
          </Button>
        </div>
      </header>

      <div
        className="grid min-h-0 flex-1"
        style={{
          gridTemplateColumns: `minmax(24rem, ${leftPaneSize}fr) 0.25rem minmax(28rem, ${100 - leftPaneSize}fr)`,
        }}
      >
        <section className="min-h-0 overflow-y-auto bg-background">
          <div className="mx-auto grid max-w-3xl gap-7 px-10 py-16">
            <div className="flex items-start justify-between gap-4 border-b pb-6">
              <div>
                <h2 className="text-base font-semibold">{document?.title ?? 'Selected SLM'}</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  {documentSubtitle || document?.program || 'SLM content preview'}
                </p>
              </div>
              <Button type="button" variant="outline" className="shrink-0">
                {selectedAgent.name}
              </Button>
            </div>

            {isLoading || isResolvingEval ? (
              <div className="flex items-center gap-3 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                {isResolvingEval
                  ? 'Checking for existing evaluation…'
                  : 'Loading SLM content...'}
              </div>
            ) : null}

            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {getErrorMessage(error, 'Unable to load the selected document.')}
              </div>
            ) : null}

            {isResolveError && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div className="flex-1">
                    <p className="font-medium">{getErrorMessage(resolveError, 'Failed to start evaluation.')}</p>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() => refetchResolve()}
                    >
                      Retry
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {!isLoading && !error ? (
              <article className="space-y-6 text-xl leading-9 text-muted-foreground">
                {documentTextGroups.length > 0 ? (
                  documentTextGroups.map((group) => (
                    <section key={group.documentId} className="space-y-5">
                      <div>
                        <h3 className="text-base font-semibold leading-6 text-foreground">
                          Document {group.documentId}
                        </h3>
                        <p className="text-sm leading-5 text-muted-foreground">Extracted text</p>
                      </div>
                      {group.chunks.map((chunk) => (
                        <section key={chunk.chunkId} className="space-y-2">
                          <p className="text-sm font-semibold leading-5 text-foreground">
                            Page {chunk.pageNumber}
                          </p>
                          {chunk.text.split(/\n{2,}/).map((paragraph, paragraphIndex) => (
                            <p key={`${chunk.chunkId}-${paragraphIndex}`}>{paragraph}</p>
                          ))}
                        </section>
                      ))}
                    </section>
                  ))
                ) : (
                  <p>
                    No extracted SLM text is available yet. The document metadata is loaded, but
                    preprocessing has not produced structured content for this file.
                  </p>
                )}
              </article>
            ) : null}

            <FlagList flags={selectedScore.evidenceFlags} />
          </div>
        </section>

        <button
          type="button"
          className="group relative min-h-0 cursor-col-resize bg-border outline-none transition-colors hover:bg-foreground/50 focus-visible:bg-foreground/50"
          onPointerDown={handleDividerPointerDown}
          aria-label="Resize document and score panels"
        >
          <span className="absolute inset-y-0 left-1/2 w-1 -translate-x-1/2" />
        </button>

        <section className="min-h-0 overflow-y-auto bg-card">
          <div className="flex min-h-44 items-center justify-between gap-6 border-b px-10">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
                Score Matrix Dashboard
              </p>
              <h2 className="mt-3 text-2xl font-semibold tracking-normal">
                Synthesized Agent View
              </h2>
              <p className="mt-2 text-base text-muted-foreground">
                Advisory synthesis - Human review authoritative
              </p>
            </div>
            {domainScore ? (
              <div className="grid size-28 place-items-center rounded-full p-3" style={scoreRingStyle}>
                <div className="grid size-full place-items-center rounded-full bg-background">
                  <div className="text-center">
                    <div className="text-3xl font-bold">{selectedScore.score}</div>
                    <div className="text-xs text-muted-foreground">score</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid size-28 place-items-center rounded-full border-2 border-dashed border-muted-foreground/25 p-3">
                <div className="text-center">
                  <Loader2 className="mx-auto size-6 animate-spin text-muted-foreground" aria-hidden="true" />
                  <div className="mt-1 text-xs text-muted-foreground">
                    {isInProgress ? 'Running...' : 'No data'}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="px-10 py-8">
            <EvaluationStatusBanner status={status?.status ? `Evaluation status: ${status.status}` : undefined} />

            {isResultsError && isTerminal && (
              <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div className="flex-1">
                    <p className="font-medium">Failed to load results</p>
                    <p className="mt-1 text-destructive/80">
                      {getErrorMessage(resultsError, 'Results could not be retrieved.')}
                    </p>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() => refetchResults()}
                    >
                      Retry
                    </Button>
                  </div>
                </div>
              </div>
            )}

            <p className="mb-4 mt-8 text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
              Evaluation Agent
            </p>
            <div className="grid gap-3 xl:grid-cols-2">
              {agents.map((agent) => {
                const Icon = agent.icon;
                const isActive = agent.id === selectedAgentId;

                return (
                  <button
                    key={agent.name}
                    type="button"
                    onClick={() => setSelectedAgentId(agent.id)}
                    className={cn(
                      'flex min-h-20 items-center gap-4 rounded-lg border p-4 text-left shadow-sm transition-colors',
                      isActive
                        ? 'border-foreground bg-foreground text-background'
                        : 'bg-background hover:bg-muted/60',
                    )}
                    aria-pressed={isActive}
                  >
                    <span
                      className={cn(
                        'grid size-12 shrink-0 place-items-center rounded-lg',
                        isActive ? 'bg-background/15' : 'bg-muted',
                      )}
                    >
                      <Icon className="size-5" aria-hidden="true" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{agent.name}</span>
                      <span
                        className={cn(
                          'mt-1 block text-sm',
                          isActive ? 'text-background/75' : 'text-muted-foreground',
                        )}
                      >
                        {agent.subtitle}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>

            <section className="mt-10 grid gap-4">
              <div className="flex items-start gap-4">
                <CheckCircle2
                  className="mt-1 size-5 shrink-0 text-emerald-600"
                  aria-hidden="true"
                />
                <div>
                  <h3 className="text-lg font-semibold">{selectedAgent.name}</h3>
                  <p className="mt-2 max-w-3xl text-muted-foreground">{selectedScore.summary}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {domainScore ? (
                  <span className="rounded-md bg-foreground px-3 py-1.5 text-sm font-semibold text-background">
                    {selectedScore.score}% individual score
                  </span>
                ) : (
                  <span className="rounded-md border px-3 py-1.5 text-sm text-muted-foreground">
                    {isInProgress ? 'Evaluating…' : '—'}
                  </span>
                )}
                <span className="rounded-md border px-3 py-1.5 text-sm text-muted-foreground">
                  {selectedScore.verdict}
                </span>
              </div>

              <div className="rounded-lg border bg-background">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[8rem] uppercase tracking-[0.18em]">Rating</TableHead>
                      <TableHead className="uppercase tracking-[0.18em]">
                        Evaluation Criterion
                      </TableHead>
                      <TableHead className="w-[14rem] uppercase tracking-[0.18em]">
                        Status
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {selectedScore.rows.length > 0 ? (
                      selectedScore.rows.map((row) => (
                        <TableRow key={row.criterion}>
                          <TableCell>
                            <span className="inline-grid size-9 place-items-center rounded-full bg-muted font-semibold">
                              {row.rating}
                            </span>
                          </TableCell>
                          <TableCell className="whitespace-normal text-muted-foreground">{row.criterion}</TableCell>
                          <TableCell className="whitespace-normal">
                            <span className="rounded-md border px-2 py-1 text-xs text-muted-foreground">
                              {row.status}
                            </span>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={3} className="py-8 text-center text-sm text-muted-foreground">
                          {isInProgress ? 'Criteria will appear once evaluation completes.' : 'No criteria available.'}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>

              <FeedbackPanel comments={selectedScore.feedbackComments} />
            </section>

            <section className="mt-8 rounded-lg border bg-background p-5">
              <div className="flex items-center gap-2">
                <Target className="size-4 text-muted-foreground" aria-hidden="true" />
                <h3 className="font-semibold">Reviewer Decision</h3>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Human reviewer may accept the advisory score, revise the agent finding, or return
                the document for clarification before final review.
              </p>
            </section>
          </div>
        </section>
      </div>
    </section>
  );
}
