import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from '@tanstack/react-router';
import { ArrowLeft, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { documentsApi } from '@/shared/api/documents.api';
import { getErrorMessage } from '@/shared/api/http';
import type { ClientDocumentChunk } from '@/shared/types/documents';
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
    <section className="flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-white">
      <header className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            to="/syllabus-alignment"
            className="inline-flex size-9 items-center justify-center border border-slate-300 text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
            aria-label="Back to SLM list"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
          </Link>
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-wider text-[#1b3b87]">
              Advisory syllabus alignment
            </p>
            <h1 className="truncate text-lg font-bold text-slate-950">
              {documentQuery.data?.title ?? 'Loading SLM…'}
            </h1>
          </div>
        </div>
        {isAlignmentComplete(run) && (
          <AlignmentReportActions run={run} />
        )}
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-2">
        <section className="flex min-h-0 flex-col border-r border-slate-200 bg-slate-50">
          <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700">SLM content</span>
            {activePage && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPageIndex((value) => Math.max(0, value - 1))}
                  disabled={pageIndex === 0}
                  className="inline-flex size-8 items-center justify-center border border-slate-300 disabled:opacity-40"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="size-4" />
                </button>
                <span className="text-xs font-semibold text-slate-600">Page {activePage[0]}</span>
                <button
                  type="button"
                  onClick={() => setPageIndex((value) => Math.min(pages.length - 1, value + 1))}
                  disabled={pageIndex >= pages.length - 1}
                  className="inline-flex size-8 items-center justify-center border border-slate-300 disabled:opacity-40"
                  aria-label="Next page"
                >
                  <ChevronRight className="size-4" />
                </button>
              </div>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-6">
            {documentQuery.isLoading && (
              <p className="flex items-center gap-2 text-sm text-slate-600">
                <Loader2 className="size-4 animate-spin" /> Loading content…
              </p>
            )}
            {documentQuery.isError && (
              <p className="text-sm font-semibold text-[#b91c1c]">
                {getErrorMessage(documentQuery.error, 'Unable to load the SLM.')}
              </p>
            )}
            {activePage && (
              <article className="mx-auto min-h-[36rem] max-w-3xl border border-slate-200 bg-white p-8 text-sm leading-[1.7] text-slate-800">
                {activePage[1].map((chunk) => (
                  <section
                    key={chunk.chunkId}
                    id={`chunk-${chunk.chunkId}`}
                    className="mb-6 scroll-mt-4 border-l-2 border-transparent pl-4 target:border-[#f2c811] target:bg-[#f2c811]/10"
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

        <section className="min-h-0 overflow-y-auto">
          <div className="border-b border-slate-200 p-5">
            <label htmlFor="syllabus-reference" className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Syllabus reference
            </label>
            <div className="mt-2 flex gap-2">
              <select
                id="syllabus-reference"
                value={effectiveSyllabusId}
                onChange={(event) => setSelectedSyllabusId(event.target.value)}
                disabled={active}
                className="h-10 min-w-0 flex-1 border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:bg-slate-100"
              >
                <option value="">Select a retrieval-ready syllabus</option>
                {(syllabi.data?.items ?? []).map((item) => (
                  <option key={item.document_id} value={item.document_id}>
                    {item.title}{item.course_code ? ` — ${item.course_code}` : ''}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={requestEvaluation}
                disabled={!effectiveSyllabusId || current.isLoading || active || start.isPending}
                className="h-10 bg-[#1b3b87] px-4 text-xs font-bold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {start.isPending ? 'Starting…' : run ? 'Evaluate again' : 'Evaluate'}
              </button>
            </div>
            {syllabi.isError && <p className="mt-2 text-xs font-semibold text-[#b91c1c]">Available syllabi could not be loaded.</p>}
            {!syllabi.isLoading && syllabi.data?.total === 0 && <p className="mt-2 text-xs font-semibold text-[#b91c1c]">No retrieval-ready syllabus is available.</p>}
            {current.isError && <p className="mt-2 text-xs font-semibold text-[#b91c1c]">The current alignment result could not be loaded.</p>}
            {start.isError && (
              <p className="mt-2 text-xs font-semibold text-[#b91c1c]">
                {getErrorMessage(start.error, 'Alignment could not be started.')}
              </p>
            )}
          </div>

          <AlignmentResultView
            run={run}
            linkSlmEvidence
            emptyMessage="Select a syllabus and start evaluation. The SME-configured model will compare substantial SLM topics only with that syllabus’s extracted Course Contents."
          />
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
