import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from '@tanstack/react-router';
import { ArrowLeft, PencilSimple, Spinner } from '@phosphor-icons/react';
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
          <p className="flex items-center gap-2 p-5 text-sm font-semibold text-text-muted">
            <Spinner className="size-4 animate-spin text-primary" aria-hidden="true" /> Loading report…
          </p>
        ) : current.isError ? (
          <p className="p-5 text-sm font-semibold text-destructive">The alignment report could not be loaded.</p>
        ) : (
          <AlignmentResultView run={run} />
        )}

      </div>
    </section>
  );
}
