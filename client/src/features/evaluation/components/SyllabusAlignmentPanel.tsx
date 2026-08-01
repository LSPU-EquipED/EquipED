import { useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertTriangle, BookOpen, CheckCircle2, ExternalLink, XCircle } from 'lucide-react';
import { buildApiUrl } from '@/shared/api/http';
import { evaluationApi } from '../api/evaluation.api';
import type { SyllabusAlignment } from '../types';

type Props = {
  alignment?: SyllabusAlignment | null;
  syllabusId?: string | null;
  evaluationId?: string | null;
  onRefresh: () => void;
};

const statusStyles: Record<SyllabusAlignment['status'], string> = {
  MEETS: 'border-[#3b963e]/30 bg-[#3b963e]/10 text-[#246b29]',
  PARTIALLY_MEETS: 'border-[#f2c811]/40 bg-[#f2c811]/10 text-slate-900',
  DOES_NOT_MEET: 'border-[#b91c1c]/30 bg-[#b91c1c]/5 text-[#b91c1c]',
  UNAVAILABLE: 'border-slate-300 bg-slate-50 text-slate-700',
};

export function SyllabusAlignmentPanel({
  alignment,
  syllabusId,
  evaluationId,
  onRefresh,
}: Props) {
  const effectiveId = syllabusId || alignment?.syllabus_document_id;
  const isRunning = alignment?.processing_state === 'RUNNING';
  const outcomes = useQuery({
    queryKey: ['syllabus-outcomes', effectiveId],
    queryFn: () => evaluationApi.getSyllabusOutcomes(effectiveId as string),
    enabled: Boolean(effectiveId),
    staleTime: 5 * 60 * 1000,
  });
  const startAlignment = useMutation({
    mutationFn: () => evaluationApi.startSmeSyllabusAlignment(evaluationId as string),
    onSuccess: () => onRefresh(),
  });

  useEffect(() => {
    if (!isRunning) return;
    const interval = window.setInterval(onRefresh, 2500);
    return () => window.clearInterval(interval);
  }, [isRunning, onRefresh]);

  const Icon = alignment?.status === 'MEETS'
    ? CheckCircle2
    : alignment?.status === 'DOES_NOT_MEET'
      ? XCircle
      : AlertTriangle;

  return (
    <section className="border border-slate-200 bg-white rounded-sm" aria-labelledby="syllabus-alignment-title">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 id="syllabus-alignment-title" className="flex items-center gap-2 font-bold text-slate-900">
              <BookOpen className="size-4 text-[#1b3b87]" aria-hidden="true" />
              Content-Syllabus Alignment
            </h3>
            <p className="mt-1 text-xs font-semibold text-slate-500">
              Advisory only — human review is authoritative.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {alignment && !isRunning && (
              <span className={`inline-flex items-center gap-1.5 border px-2.5 py-1 text-xs font-bold ${statusStyles[alignment.status]}`}>
                <Icon className="size-3.5" aria-hidden="true" />
                {alignment.status.replace(/_/g, ' ')}
              </span>
            )}
            <button
              type="button"
              onClick={() => startAlignment.mutate()}
              disabled={!effectiveId || !evaluationId || isRunning || startAlignment.isPending}
              className="inline-flex h-8 items-center border border-[#1b3b87] bg-[#1b3b87] px-3 text-xs font-bold uppercase tracking-wider text-white disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
            >
              {isRunning || startAlignment.isPending
                ? 'Running alignment…'
                : alignment
                  ? 'Run alignment again'
                  : 'Run content-syllabus alignment'}
            </button>
          </div>
        </div>
        {alignment ? (
          <>
            <p className="mt-3 max-w-4xl text-sm leading-relaxed text-slate-700">{alignment.statement}</p>
            {!isRunning && (
              <p className="mt-2 text-xs font-semibold text-slate-500">
                {alignment.aligned_topics} of {alignment.total_topics} substantial SLM topics aligned
              </p>
            )}
          </>
        ) : (
          <p className="mt-3 max-w-4xl text-sm leading-relaxed text-slate-700">
            This check is separate from SME scoring. Start it when you are ready to compare the SLM content with the extracted syllabus outcomes.
          </p>
        )}
        {!effectiveId && (
          <p className="mt-2 text-xs font-semibold text-[#b91c1c]">No syllabus is attached to this evaluation.</p>
        )}
        {startAlignment.isError && (
          <p className="mt-2 text-xs font-semibold text-[#b91c1c]">The alignment process could not be started.</p>
        )}
      </div>

      {effectiveId && (
        <div className="border-b border-slate-200 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">Extracted syllabus outcomes</h4>
            <a href={`${buildApiUrl(`/documents/${effectiveId}/file`)}#page=1`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-bold text-[#1b3b87] underline focus:outline-none focus:ring-2 focus:ring-[#1b3b87]">
              View source PDF <ExternalLink className="size-3" aria-hidden="true" />
            </a>
          </div>
          {outcomes.isLoading ? (
            <p className="mt-3 text-sm text-slate-500">Loading extracted outcomes…</p>
          ) : outcomes.isError ? (
            <p className="mt-3 text-sm text-[#b91c1c]">Extracted outcomes could not be loaded.</p>
          ) : (
            <div className="mt-3 overflow-x-auto border border-slate-200">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-[11px] uppercase tracking-wider text-slate-600"><tr><th className="px-3 py-2">Code</th><th className="px-3 py-2">Outcome</th><th className="px-3 py-2">Source</th></tr></thead>
                <tbody className="divide-y divide-slate-200">
                  {outcomes.data?.outcomes.map((outcome) => (
                    <tr key={outcome.chunk_id}>
                      <td className="px-3 py-2 font-bold text-slate-900">{outcome.outcome_code}</td>
                      <td className="px-3 py-2 leading-relaxed text-slate-700">{outcome.outcome_text}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                        <a
                          href={`${buildApiUrl(`/documents/${effectiveId}/file`)}#page=${outcome.page_number}`}
                          target="_blank"
                          rel="noreferrer"
                          className="font-bold text-[#1b3b87] underline"
                        >
                          Page {outcome.page_number}
                        </a>{' '}
                        · {outcome.extraction_method === 'ocr' ? 'OCR' : 'PDF text'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {alignment && !isRunning && (
      <div className="grid gap-4 p-5 lg:grid-cols-2">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">Supported topic matches</h4>
          <div className="mt-2 space-y-2">
            {alignment.outcome_matches.length ? alignment.outcome_matches.map((match) => (
              <article key={match.topic_id} className="border border-[#3b963e]/25 bg-[#3b963e]/5 p-3">
                <p className="text-sm font-bold text-slate-900">{match.topic}</p>
                <p className="mt-1 text-xs text-slate-600">
                  <a href={`#chunk-${match.slm_chunk_id}`} className="font-bold text-[#1b3b87] underline">
                    SLM page {match.slm_page_number ?? '—'}
                  </a>: “{match.slm_evidence}”
                </p>
                <p className="mt-2 text-xs font-semibold text-[#246b29]">
                  {effectiveId && match.page_number ? (
                    <a href={`${buildApiUrl(`/documents/${effectiveId}/file`)}#page=${match.page_number}`} target="_blank" rel="noreferrer" className="underline">
                      {match.outcome_code}, syllabus page {match.page_number}
                    </a>
                  ) : `${match.outcome_code}, syllabus page ${match.page_number ?? '—'}`}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">{match.rationale}</p>
              </article>
            )) : <p className="text-sm text-slate-500">No supported matches were recorded.</p>}
          </div>
        </div>
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">Unmatched SLM topics</h4>
          <div className="mt-2 space-y-2">
            {alignment.unmatched_topics.length ? alignment.unmatched_topics.map((topic) => (
              <article key={topic.topic_id} className="border border-[#b91c1c]/20 bg-[#b91c1c]/5 p-3">
                <p className="text-sm font-bold text-slate-900">{topic.topic}</p>
                <p className="mt-1 text-xs text-slate-600">
                  <a href={`#chunk-${topic.slm_chunk_id}`} className="font-bold text-[#1b3b87] underline">
                    SLM page {topic.slm_page_number ?? '—'}
                  </a>: “{topic.slm_evidence}”
                </p>
                <p className="mt-2 text-xs leading-relaxed text-[#b91c1c]">{topic.rationale}</p>
              </article>
            )) : <p className="text-sm text-slate-500">No unmatched topics were recorded.</p>}
          </div>
        </div>
      </div>
      )}
    </section>
  );
}
