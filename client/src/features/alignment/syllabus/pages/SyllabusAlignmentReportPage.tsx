import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from '@tanstack/react-router';
import { ArrowLeft, PencilSimple } from '@phosphor-icons/react';
import { Skeleton } from '@/shared/components/Skeleton';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES, CARD_STYLES } from '@/shared/constants/theme';
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
    <section className="min-h-full bg-canvas px-6 py-7">
      <div className={cn('mx-auto max-w-5xl', CARD_STYLES.ledger)}>
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border bg-surface p-5">
          <div className="flex items-start gap-3">
            <Link
              to="/syllabus-alignment"
              className="inline-flex size-9 items-center justify-center rounded-sm border border-border bg-surface text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
              aria-label="Back to SLM list"
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
            </Link>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-primary">
                Syllabus alignment report
              </p>
              <h1 className="mt-1 text-2xl font-bold text-text">
                {run?.slm_title ?? 'Alignment result'}
              </h1>
              <p className="mt-2 text-sm text-text-muted">
                Advisory only. Human CID review remains authoritative and this result does not
                change rubric scores.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/syllabus-alignment/$documentId"
              params={{ documentId }}
              className={cn(BUTTON_STYLES.base, BUTTON_STYLES.variants.secondary, BUTTON_STYLES.sizes.sm)}
            >
              <PencilSimple className="size-4" aria-hidden="true" /> Evaluate again
            </Link>
            {isAlignmentComplete(run) && (
              <AlignmentReportActions run={run} />
            )}
          </div>
        </header>

        {current.isLoading ? (
          <div
            className="space-y-5 p-5"
            role="status"
            aria-label="Loading syllabus alignment report"
          >
            <div className="grid gap-3 sm:grid-cols-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="space-y-2 rounded-sm border border-border bg-surface-subtle p-4">
                  <Skeleton className="h-2.5 w-24" />
                  <Skeleton className="h-7 w-20" />
                </div>
              ))}
            </div>
            <div className="space-y-4 rounded-sm border border-border p-5">
              <Skeleton className="h-4 w-44" />
              {Array.from({ length: 7 }).map((_, index) => (
                <div key={index} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem]">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-24 sm:ml-auto" />
                </div>
              ))}
            </div>
          </div>
        ) : current.isError ? (
          <p className="p-5 text-sm font-semibold text-destructive">The alignment report could not be loaded.</p>
        ) : (
          <AlignmentResultView run={run} />
        )}

      </div>
    </section>
  );
}
