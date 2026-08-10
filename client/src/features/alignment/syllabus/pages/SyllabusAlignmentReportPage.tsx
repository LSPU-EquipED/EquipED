import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from '@tanstack/react-router';
import { ArrowLeft, Edit3, Loader2 } from 'lucide-react';
import { alignmentApi } from '../api/syllabusAlignment.api';
import { AlignmentReportActions } from '../components/AlignmentReportActions';
import { AlignmentResultView } from '../components/AlignmentResultView';
import { isAlignmentComplete } from '../utils/alignmentPresentation';

export function SyllabusAlignmentReportPage() {
  const { documentId } = useParams({ strict: false }) as { documentId: string };
  const current = useQuery({
    queryKey: ['syllabus-alignment-current', documentId],
    queryFn: () => alignmentApi.getCurrent(documentId),
  });
  const run = current.data ?? null;

  return (
    <section className="min-h-full bg-slate-50 px-6 py-7">
      <div className="mx-auto max-w-5xl border border-slate-200 bg-white">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 p-5">
          <div className="flex items-start gap-3">
            <Link
              to="/syllabus-alignment"
              className="inline-flex size-9 items-center justify-center border border-slate-300 text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
              aria-label="Back to SLM list"
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
            </Link>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-[#1b3b87]">
                Syllabus alignment report
              </p>
              <h1 className="mt-1 text-2xl font-bold text-slate-950">
                {run?.slm_title ?? 'Alignment result'}
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                Advisory only. Human CID review remains authoritative and this result does not
                change rubric scores.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/syllabus-alignment/$documentId"
              params={{ documentId }}
              className="inline-flex h-9 items-center gap-2 border border-slate-300 bg-white px-3 text-xs font-bold uppercase tracking-wide text-slate-700"
            >
              <Edit3 className="size-4" aria-hidden="true" /> Evaluate again
            </Link>
            {isAlignmentComplete(run) && (
              <AlignmentReportActions run={run} />
            )}
          </div>
        </header>

        {current.isLoading ? (
          <p className="flex items-center gap-2 p-5 text-sm font-semibold text-slate-600">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading report…
          </p>
        ) : current.isError ? (
          <p className="p-5 text-sm font-semibold text-[#b91c1c]">The alignment report could not be loaded.</p>
        ) : (
          <AlignmentResultView run={run} />
        )}

      </div>
    </section>
  );
}
