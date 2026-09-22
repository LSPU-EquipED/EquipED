import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from '@tanstack/react-router';
import { ArrowLeft, CaretLeft, CaretRight, Warning, FileText } from '@phosphor-icons/react';
import { Button } from '@equiped/ui';
import { Skeleton } from '@equiped/ui';
import { cn } from '@equiped/ui';
import { documentsApi } from '@equiped/api-client';
import { getErrorMessage } from '@equiped/api-client';
import type { ClientDocumentChunk } from '@equiped/types';
import { alignmentApi } from '../api/syllabusAlignment.api';
import { AlignmentReportActions } from '../components/AlignmentReportActions';
import { AlignmentResultView } from '../components/AlignmentResultView';
import { ReplaceAlignmentModal } from '../components/ReplaceAlignmentModal';
import {
  isAlignmentActive,
  isAlignmentComplete,
  shouldConfirmAlignmentReplacement,
} from '../utils/alignmentPresentation';

export function SyllabusAlignmentWorkspacePage() {
  const { documentId } = useParams({ strict: false }) as { documentId: string };
  const queryClient = useQueryClient();
  const [selectedSyllabusId, setSelectedSyllabusId] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [confirmReplace, setConfirmReplace] = useState(false);

  // ADR 0006: Reset selectedSyllabusId, pageIndex, and replacement state whenever documentId changes
  useEffect(() => {
    setSelectedSyllabusId('');
    setPageIndex(0);
    setConfirmReplace(false);
  }, [documentId]);

  const documentQuery = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => documentsApi.getDocument(documentId),
  });
  const syllabi = useQuery({
    queryKey: ['available-syllabus-references'],
    queryFn: alignmentApi.getAvailableSyllabi,
    staleTime: 60_000,
  });
  const current = useQuery({
    queryKey: ['syllabus-alignment-current', documentId],
    queryFn: () => alignmentApi.getCurrent(documentId),
    refetchInterval: (query) => (isAlignmentActive(query.state.data) ? 2000 : false),
  });
  const run = current.data ?? null;
  const effectiveSyllabusId = selectedSyllabusId || run?.syllabus_document_id || '';

  useEffect(() => {
    if (run && !isAlignmentActive(run)) {
      void queryClient.invalidateQueries({ queryKey: ['syllabus-alignment-slms'] });
    }
  }, [queryClient, run]);

  const start = useMutation({
    mutationFn: () => alignmentApi.start(documentId, effectiveSyllabusId),
    onSuccess: (created) => {
      setSelectedSyllabusId(created.syllabus_document_id);
      setConfirmReplace(false);
      queryClient.setQueryData(['syllabus-alignment-current', documentId], created);
      void queryClient.invalidateQueries({ queryKey: ['syllabus-alignment-slms'] });
    },
  });

  const pages = useMemo(() => {
    const grouped = new Map<number, ClientDocumentChunk[]>();
    for (const chunk of documentQuery.data?.chunks ?? []) {
      const values = grouped.get(chunk.pageNumber) ?? [];
      values.push(chunk);
      grouped.set(chunk.pageNumber, values);
    }
    return [...grouped.entries()].sort(([a], [b]) => a - b);
  }, [documentQuery.data?.chunks]);
  const activePage = pages[pageIndex] ?? pages[0];
  const active = isAlignmentActive(run);

  const requestEvaluation = () => {
    if (!effectiveSyllabusId || current.isLoading || active || start.isPending) return;
    if (shouldConfirmAlignmentReplacement(run)) setConfirmReplace(true);
    else start.mutate();
  };

  return (
    <section className="flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-canvas">
      {/* Top Header */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2.5 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            to="/syllabus-alignment"
            className="inline-flex size-8 items-center justify-center rounded-sm border border-border bg-surface text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Back to SLM list"
          >
            <ArrowLeft className="size-3.5" aria-hidden="true" />
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-text">
              {documentQuery.isLoading ? (
                <Skeleton className="h-5 w-56 max-w-[60vw]" />
              ) : (
                documentQuery.data?.title
              )}
            </h1>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isAlignmentComplete(run) && (
            <>
              <Link
                to="/syllabus-alignment/$documentId/report"
                params={{ documentId }}
                className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle"
              >
                <FileText className="size-3.5 text-text-muted" aria-hidden="true" />
                <span>View Full Report</span>
              </Link>
              <AlignmentReportActions run={run} />
            </>
          )}
        </div>
      </header>

      {/* Integrated Split Workbench Grid */}
      <div className="grid min-h-0 flex-1 grid-cols-1 divide-y divide-border overflow-hidden bg-surface lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] lg:divide-y-0 lg:divide-x">
        {/* Left Pane: SLM Reader */}
        <section className="flex min-h-0 flex-col bg-canvas">
          <div className="flex items-center justify-between border-b border-border bg-surface-subtle/50 px-4 py-2.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-text">SLM Document Content</span>
            {activePage && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPageIndex((value) => Math.max(0, value - 1))}
                  disabled={pageIndex === 0}
                  className="inline-flex size-7 items-center justify-center rounded-sm border border-border bg-surface text-text transition-colors hover:bg-surface-subtle disabled:opacity-40 disabled:hover:bg-surface"
                  aria-label="Previous page"
                >
                  <CaretLeft className="size-3.5" />
                </button>
                <span className="text-xs font-semibold tabular-nums text-text-muted">
                  Page {activePage[0]} of {pages.length}
                </span>
                <button
                  type="button"
                  onClick={() => setPageIndex((value) => Math.min(pages.length - 1, value + 1))}
                  disabled={pageIndex >= pages.length - 1}
                  className="inline-flex size-7 items-center justify-center rounded-sm border border-border bg-surface text-text transition-colors hover:bg-surface-subtle disabled:opacity-40 disabled:hover:bg-surface"
                  aria-label="Next page"
                >
                  <CaretRight className="size-3.5" />
                </button>
              </div>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
            {documentQuery.isLoading && (
              <div role="status" aria-label="Loading SLM content" className="space-y-4">
                <Skeleton className="h-4 w-40" />
                <div className="space-y-3 rounded-md border border-border bg-surface p-8 shadow-none">
                  {Array.from({ length: 12 }).map((_, index) => (
                    <Skeleton key={index} className={cn('h-3', index % 5 === 4 ? 'w-2/3' : 'w-full')} />
                  ))}
                </div>
              </div>
            )}
            {documentQuery.isError && (
              <div className="flex items-center gap-2 rounded-sm border border-destructive/25 bg-destructive-soft p-3.5 text-xs font-medium text-destructive">
                <Warning className="size-4 shrink-0" aria-hidden="true" />
                <span>{getErrorMessage(documentQuery.error, 'Unable to load the SLM.')}</span>
              </div>
            )}
            {activePage && (
              <article className="mx-auto min-h-[36rem] max-w-3xl rounded-md border border-border bg-surface p-6 sm:p-8 text-sm leading-[1.7] text-text shadow-none">
                {activePage[1].map((chunk) => (
                  <section
                    key={chunk.chunkId}
                    id={`chunk-${chunk.chunkId}`}
                    className="mb-6 scroll-mt-4 rounded-xs border-l-2 border-transparent pl-4 transition-colors target:border-primary target:bg-primary-soft/40"
                  >
                    {chunk.text.split(/\n{2,}/).map((paragraph, index) => (
                      <p key={`${chunk.chunkId}-${index}`} className="mb-3">{paragraph}</p>
                    ))}
                  </section>
                ))}
              </article>
            )}
          </div>
        </section>

        {/* Right Pane: Syllabus Alignment Dossier */}
        <section className="flex min-h-0 flex-col overflow-y-auto bg-surface">
          <div className="border-b border-border bg-surface-subtle/50 p-4 sm:p-5">
            <label htmlFor="syllabus-reference" className="mb-1.5 block text-xs font-semibold text-text">
              Target Syllabus Reference
            </label>
            <div className="flex gap-2">
              <select
                id="syllabus-reference"
                value={effectiveSyllabusId}
                onChange={(event) => setSelectedSyllabusId(event.target.value)}
                disabled={active || start.isPending}
                className="h-8.5 min-w-0 flex-1 rounded-sm border border-input bg-surface px-3 text-xs font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent disabled:bg-surface-subtle disabled:text-text-muted"
              >
                <option value="">Select a retrieval-ready syllabus...</option>
                {(syllabi.data?.items ?? []).map((item) => (
                  <option key={item.document_id} value={item.document_id}>
                    {item.title}{item.course_code ? ` — ${item.course_code}` : ''}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={requestEvaluation}
                disabled={!effectiveSyllabusId || current.isLoading || active || start.isPending}
                isLoading={start.isPending}
                className="h-8.5 px-4 font-semibold text-xs whitespace-nowrap"
              >
                {start.isPending ? 'Starting…' : run ? 'Evaluate again' : 'Evaluate'}
              </Button>
            </div>
            {syllabi.isError && (
              <p className="mt-2 text-xs font-semibold text-destructive">Available syllabi could not be loaded.</p>
            )}
            {!syllabi.isLoading && syllabi.data?.total === 0 && (
              <p className="mt-2 text-xs font-semibold text-destructive">No retrieval-ready syllabus is available.</p>
            )}
            {current.isError && (
              <p className="mt-2 text-xs font-semibold text-destructive">The current alignment result could not be loaded.</p>
            )}
            {start.isError && (
              <p className="mt-2 text-xs font-semibold text-destructive">
                {getErrorMessage(start.error, 'Alignment could not be started.')}
              </p>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            <AlignmentResultView
              run={run}
              isLoading={current.isLoading}
              linkSlmEvidence
              emptyMessage="Select a syllabus and start evaluation. The SME-configured model will compare substantial SLM topics only with that syllabus’s extracted Course Contents."
            />
          </div>
        </section>
      </div>

      <ReplaceAlignmentModal
        open={confirmReplace}
        busy={start.isPending}
        onCancel={() => setConfirmReplace(false)}
        onConfirm={() => start.mutate()}
      />
    </section>
  );
}
