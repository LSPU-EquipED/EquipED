import { ClockCounterClockwise } from '@phosphor-icons/react';
import { TABLE_STYLES, TableSkeleton, TYPOGRAPHY } from '@equiped/ui';
import type { TableSkeletonColumn } from '@equiped/ui';
import { useTrainingJobs } from '../hooks/useTrainingJobs';
import { useTrainingTablePagination } from '../hooks/useTrainingTablePagination';
import { TrainingJobRow } from './TrainingJobRow';
import { TrainingTablePagination } from './TrainingTablePagination';

const LOADING_COLUMNS: TableSkeletonColumn[] = [
  { label: 'Created', skeletonClassName: 'h-4 w-24' },
  { label: 'Dataset', skeletonClassName: 'h-4 w-16' },
  { label: 'Status', skeletonClassName: 'h-5 w-20' },
  {
    label: 'Details',
    headerClassName: 'w-16',
    cellClassName: 'px-3',
    skeletonClassName: 'size-10',
  },
];

export function TrainingJobsPanel({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useTrainingJobs(agentId);
  const jobs = data?.jobs ?? [];
  const { visibleItems, pagination } = useTrainingTablePagination(jobs, agentId);

  return (
    <section aria-labelledby="run-history-title" className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="run-history-title" className={TYPOGRAPHY.headingSm}>
          Run history
        </h2>
        {!isLoading && !isError && (
          <span className="text-xs leading-5 tabular-nums text-text-muted">
            {jobs.length} {jobs.length === 1 ? 'run' : 'runs'}
          </span>
        )}
      </div>
      {isLoading ? (
        <TableSkeleton
          ariaLabel="Loading training jobs"
          className={TABLE_STYLES.wrapper}
          tableClassName="min-w-[32rem] table-fixed [&_td]:py-2"
          rows={3}
          columns={LOADING_COLUMNS}
        />
      ) : isError ? (
        <p
          role="alert"
          className="rounded-md border border-border bg-destructive-soft px-4 py-5 text-sm text-destructive"
        >
          Failed to load training jobs.
        </p>
      ) : jobs.length === 0 ? (
        <div className="flex items-start gap-3 rounded-md border border-border bg-surface px-4 py-5 sm:px-5">
          <ClockCounterClockwise
            className="mt-0.5 size-5 shrink-0 text-text-muted"
            aria-hidden="true"
          />
          <div className="space-y-1">
            <p className="text-sm font-medium text-text">No training runs yet.</p>
            <p className="text-sm leading-5 text-text-muted">
              Prepare a run above to record a dataset snapshot.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className={TABLE_STYLES.wrapper}>
            <table
              className={`${TABLE_STYLES.table} min-w-[32rem] table-fixed`}
              aria-label="Training run history"
            >
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Created
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Dataset
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Status
                  </th>
                  <th scope="col" className="w-16">
                    <span className="sr-only">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {visibleItems.map((job) => (
                  <TrainingJobRow key={job.job_id} job={job} />
                ))}
              </tbody>
            </table>
          </div>
          <TrainingTablePagination label="Run history" pagination={pagination} />
        </>
      )}
    </section>
  );
}
