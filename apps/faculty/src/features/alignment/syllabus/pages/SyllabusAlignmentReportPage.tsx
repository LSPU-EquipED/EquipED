import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from '@tanstack/react-router';
import { ArrowLeft, PencilSimple } from '@phosphor-icons/react';
import { alignmentApi } from '../api/syllabusAlignment.api';
import { AlignmentReportActions } from '../components/AlignmentReportActions';
import {
  AlignmentResultView,
  AlignmentResultViewSkeleton,
} from '../components/AlignmentResultView';
import { isAlignmentComplete } from '../utils/alignmentPresentation';

export function SyllabusAlignmentReportPage() {
  const { documentId } = useParams({ strict: false }) as { documentId: string };
  const current = useQuery({
    queryKey: ['syllabus-alignment-current', documentId],
    queryFn: () => alignmentApi.getCurrent(documentId),
    enabled: Boolean(documentId),
  });

  const run = current.data ?? null;

  return (
    <section className="px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl overflow-hidden rounded-md border border-border bg-surface">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-5 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link
              to="/syllabus-alignment/$documentId"
              params={{ documentId }}
              className="inline-flex size-8 items-center justify-center rounded-sm border border-border bg-surface text-text transition-colors hover:bg-surface-subtle"
              aria-label="Back to workspace"
            >
              <ArrowLeft className="size-3.5" aria-hidden="true" />
            </Link>
            <div>
              <h1 className="text-base font-semibold text-text">Syllabus Alignment Report</h1>
              <p className="text-xs text-text-muted">
                {run?.slm_title ?? 'Loaded SLM'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/syllabus-alignment/$documentId"
              params={{ documentId }}
              className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle"
            >
              <PencilSimple className="size-3.5 text-text-muted" aria-hidden="true" />
              <span>Evaluate again</span>
            </Link>
            {isAlignmentComplete(run) && (
              <AlignmentReportActions run={run} />
            )}
          </div>
        </header>

        {current.isLoading ? (
          <AlignmentResultViewSkeleton />
        ) : current.isError ? (
          <p className="p-5 text-sm font-semibold text-destructive">The alignment report could not be loaded.</p>
        ) : (
          <AlignmentResultView run={run} />
        )}
      </div>
    </section>
  );
}
