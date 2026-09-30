import { TABLE_STYLES, TableSkeleton, TYPOGRAPHY } from '@equiped/ui';
import { useTrainingJobs } from '../hooks/useTrainingJobs';
import { TrainingJobRow } from './TrainingJobRow';

export function TrainingJobsPanel({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useTrainingJobs(agentId);
  const jobs = data?.jobs ?? [];

  return (
    <section aria-labelledby="run-history-title" className="space-y-3">
      <div className="flex items-baseline gap-3">
        <h2 id="run-history-title" className={TYPOGRAPHY.headingSm}>
          Run history
        </h2>
        {!isLoading && !isError && (
          <span className="text-sm tabular-nums text-text-muted">
            {jobs.length} {jobs.length === 1 ? 'run' : 'runs'}
          </span>
        )}
      </div>
      {isLoading ? (
        <TableSkeleton
          ariaLabel="Loading training jobs"
          columns={[
            { label: 'Created', skeletonClassName: 'h-4 w-24' },
            { label: 'Dataset', skeletonClassName: 'h-4 w-16' },
            { label: 'Status', skeletonClassName: 'h-5 w-20' },
            { label: 'Details', skeletonClassName: 'h-4 w-8' },
          ]}
        />
      ) : isError ? (
        <p role="alert" className="border-y border-border py-5 text-sm text-destructive">
          Failed to load training jobs.
        </p>
      ) : jobs.length === 0 ? (
        <p className="border-y border-border py-5 text-sm text-text-muted">No training runs yet.</p>
      ) : (
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
                <th scope="col" className="w-14">
                  <span className="sr-only">Details</span>
                </th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {jobs.map((job) => (
                <TrainingJobRow key={job.job_id} job={job} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
