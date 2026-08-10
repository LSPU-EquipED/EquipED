import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { AlertTriangle, BookOpenCheck, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { alignmentApi } from '../api/syllabusAlignment.api';
import type { AlignmentLevel, AlignmentProcessingStatus } from '../types';

const levelLabels: Record<AlignmentLevel, string> = {
  MEETS: 'Meets',
  PARTIALLY_MEETS: 'Partially meets',
  DOES_NOT_MEET: 'Does not meet',
  UNAVAILABLE: 'Unavailable',
};

function statusLabel(status: AlignmentProcessingStatus, level?: AlignmentLevel | null) {
  if (status === 'COMPLETED' && level) return levelLabels[level];
  if (status === 'FAILED') return 'Unavailable';
  return status === 'QUEUED' ? 'Queued' : 'Running';
}

export function SyllabusAlignmentPage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const slms = useQuery({
    queryKey: ['syllabus-alignment-slms', page],
    queryFn: () => alignmentApi.listSlms(page, pageSize),
    refetchInterval: (query) =>
      (query.state.data?.items ?? []).some((item) =>
        ['QUEUED', 'RUNNING'].includes(item.current_result?.status ?? ''),
      )
        ? 3000
        : false,
  });
  const totalPages = Math.max(1, Math.ceil((slms.data?.total ?? 0) / pageSize));

  return (
    <section className="px-6 py-7">
      <header className="border-b border-slate-200 pb-5">
        <div className="flex items-center gap-3">
          <BookOpenCheck className="size-6 text-[#1b3b87]" aria-hidden="true" />
          <div>
            <h1 className="text-2xl font-bold text-slate-950">Syllabus Alignment</h1>
            <p className="mt-1 text-sm text-slate-600">
              Check whether substantial SLM topics are included in an approved syllabus.
            </p>
          </div>
        </div>
      </header>

      {slms.isLoading && (
        <div className="flex items-center gap-2 border-b border-slate-200 py-6 text-sm font-semibold text-slate-600">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading SLM documents…
        </div>
      )}
      {slms.isError && (
        <div className="mt-5 flex items-center gap-2 border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-4 text-sm font-semibold text-[#b91c1c]">
          <AlertTriangle className="size-4" aria-hidden="true" />
          {getErrorMessage(slms.error, 'Unable to load SLM documents.')}
        </div>
      )}
      {!slms.isLoading && !slms.isError && slms.data?.items.length === 0 && (
        <p className="mt-5 border border-dashed border-slate-300 p-5 text-sm text-slate-600">
          No SLM documents are available. Upload an SLM before starting syllabus alignment.
        </p>
      )}
      {!!slms.data?.items.length && (
        <div className="mt-5 border border-slate-200 bg-white">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-[11px] uppercase tracking-wider text-slate-600">
                <tr>
                  <th className="px-4 py-3">SLM document</th>
                  <th className="px-4 py-3">Program / course</th>
                  <th className="px-4 py-3">Current alignment</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {slms.data.items.map((item) => (
                  <tr key={item.document_id}>
                    <td className="px-4 py-3">
                      <p className="font-bold text-slate-900">{item.title}</p>
                      <p className="mt-0.5 text-xs text-slate-600">
                        {item.lesson_title || item.course_title || 'No lesson title'}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {[item.program, item.course_code].filter(Boolean).join(' · ') ||
                        'Not specified'}
                    </td>
                    <td className="px-4 py-3">
                      {item.current_result ? (
                        <div>
                          <span className="inline-flex border border-slate-300 bg-slate-50 px-2 py-1 text-xs font-bold uppercase tracking-wide text-slate-700">
                            {statusLabel(item.current_result.status, item.current_result.alignment_level)}
                          </span>
                          <p className="mt-1 text-xs text-slate-500">
                            {item.current_result.syllabus_title}
                          </p>
                        </div>
                      ) : (
                        <span className="text-xs font-semibold text-slate-500">
                          Not yet evaluated
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {item.evaluation_available ? (
                        <div className="flex flex-wrap justify-end gap-2">
                          {item.current_result?.status === 'COMPLETED' ? (
                            <Link
                              to="/syllabus-alignment/$documentId"
                              params={{ documentId: item.document_id }}
                              className="inline-flex h-9 items-center gap-2 border border-[#1b3b87] bg-white px-3 text-xs font-bold uppercase tracking-wide text-[#1b3b87] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                            >
                              View Result
                            </Link>
                          ) : ['QUEUED', 'RUNNING'].includes(item.current_result?.status ?? '') ? (
                            <button
                              type="button"
                              disabled
                              className="inline-flex h-9 items-center gap-2 bg-slate-300 px-3 text-xs font-bold uppercase tracking-wide text-slate-600"
                            >
                              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> Running
                            </button>
                          ) : (
                            <Link
                              to="/syllabus-alignment/$documentId"
                              params={{ documentId: item.document_id }}
                              className="inline-flex h-9 items-center gap-2 rounded-sm bg-[#1b3b87] px-3 text-xs font-bold uppercase tracking-wide text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                            >
                              {item.current_result?.status === 'FAILED'
                                  ? 'Retry'
                                  : 'Evaluate'}
                              <ChevronRight className="size-3.5" aria-hidden="true" />
                            </Link>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs font-semibold text-slate-500">
                          Processing unavailable
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <footer className="flex items-center justify-between border-t border-slate-200 px-4 py-3">
              <p className="text-xs font-semibold text-slate-600">
                Page {page} of {totalPages} · {slms.data.total} SLM documents
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  disabled={page === 1 || slms.isFetching}
                  className="inline-flex h-8 items-center gap-1 border border-slate-300 px-2 text-xs font-bold text-slate-700 disabled:opacity-40"
                >
                  <ChevronLeft className="size-3.5" aria-hidden="true" /> Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  disabled={page === totalPages || slms.isFetching}
                  className="inline-flex h-8 items-center gap-1 border border-slate-300 px-2 text-xs font-bold text-slate-700 disabled:opacity-40"
                >
                  Next <ChevronRight className="size-3.5" aria-hidden="true" />
                </button>
              </div>
            </footer>
          )}
        </div>
      )}
    </section>
  );
}
