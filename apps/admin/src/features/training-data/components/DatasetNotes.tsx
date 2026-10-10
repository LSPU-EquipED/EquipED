import { Skeleton } from '@equiped/ui';
import type { DatasetReadiness, ReadinessSummary } from '../types';
import { describeFunnel, RULE_OF_THUMB_NOTE, SEEDED_DATA_NOTE } from '../utils/trainingData.utils';
import '../styles/DatasetNotes.css';

interface DatasetNotesProps {
  data: Pick<DatasetReadiness, 'pair_count' | 'skipped_counts'> | undefined;
  readiness: ReadinessSummary | null;
  comparison: string | null;
  reviewerNote: string | null;
  isLoading: boolean;
  isError: boolean;
}

export function DatasetNotes({
  data,
  readiness,
  comparison,
  reviewerNote,
  isLoading,
  isError,
}: DatasetNotesProps) {
  return (
    <div className="min-w-0 border-t border-border bg-surface-subtle/30 p-4 sm:p-5 lg:border-t-0 lg:border-l">
      <h3 className="text-sm font-medium leading-5 text-text">Notes</h3>
      {isLoading ? (
        <div aria-hidden="true" className="mt-3 space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="mt-4 h-5 w-44" />
        </div>
      ) : isError || !data || !readiness ? (
        <p className="mt-3 text-[13px] leading-5 text-text-muted">
          Notes will appear once the check finishes.
        </p>
      ) : (
        <div className="mt-3 divide-y divide-border text-[13px] leading-5">
          <div role="note" className="space-y-1 pb-3 text-text-muted">
            <p>{SEEDED_DATA_NOTE}</p>
            {reviewerNote && <p>{reviewerNote}</p>}
          </div>
          {(readiness.tier !== 'reasonable' || comparison) && (
            <div className="space-y-1 py-3">
              {readiness.tier !== 'reasonable' && (
                <p className="font-medium text-text">{readiness.message}</p>
              )}
              {comparison && <p className="text-text-muted">{comparison}</p>}
            </div>
          )}
          <details className="dataset-inclusion-details pt-3 text-text-muted">
            <summary className="w-fit cursor-pointer rounded-sm font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              How these counts were worked out
            </summary>
            <div className="space-y-2 pt-2">
              {readiness.tier === 'reasonable' && <p>{readiness.message}</p>}
              {(readiness.tier === 'small' || readiness.tier === 'reasonable') && (
                <p>{RULE_OF_THUMB_NOTE}</p>
              )}
              <p className="border-t border-border pt-2">
                {describeFunnel(data.pair_count, data.skipped_counts)}
              </p>
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
