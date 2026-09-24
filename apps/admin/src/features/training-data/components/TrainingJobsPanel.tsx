import { useState } from 'react';
import { Database, Rocket, Warning } from '@phosphor-icons/react';
import { Badge, Button, CARD_STYLES, TABLE_STYLES, TableSkeleton, cn } from '@equiped/ui';
import type { StatusVariant } from '@equiped/ui';
import { useStartTrainingJob } from '../hooks/useStartTrainingJob';
import { useTrainingJobs } from '../hooks/useTrainingJobs';
import type { TrainingJobCreateResponse, TrainingJobItem } from '../types';
import { shortHash } from '../utils/trainingData.utils';
import { TrainingJobCredentials } from './TrainingJobCredentials';

function getJobStatusVariant(status: string): StatusVariant {
  if (status === 'completed') return 'success';
  if (status === 'downloaded') return 'info';
  return 'neutral';
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function TrainingJobsPanel({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useTrainingJobs(agentId);
  const startJob = useStartTrainingJob(agentId);
  const [lastCreated, setLastCreated] = useState<TrainingJobCreateResponse | null>(null);

  const handleStart = () => {
    setLastCreated(null);
    startJob.mutate(undefined, {
      onSuccess: (result) => {
        setLastCreated(result);
      },
    });
  };

  const jobs = data?.jobs ?? [];

  return (
    <div className={CARD_STYLES.ledger}>
      <div className={CARD_STYLES.header}>
        <div className="flex items-center gap-2">
          <Rocket className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-text">Training Jobs</h2>
        </div>
        <Button onClick={handleStart} disabled={startJob.isPending} isLoading={startJob.isPending}>
          {startJob.isPending ? 'Starting…' : 'Start Training Job'}
        </Button>
      </div>

      {startJob.isError ? (
        <div className="flex items-center gap-2.5 border-b border-border bg-destructive-soft px-5 py-3 text-sm font-semibold text-destructive">
          <Warning className="size-4 shrink-0" aria-hidden="true" />
          <span>
            {startJob.error instanceof Error
              ? startJob.error.message
              : 'Failed to start training job.'}
          </span>
        </div>
      ) : null}

      {lastCreated ? <TrainingJobCredentials credentials={lastCreated} /> : null}

      {isLoading ? (
        <TableSkeleton
          ariaLabel="Loading training jobs"
          columns={[
            { label: 'Job ID', skeletonClassName: 'h-4 w-40' },
            { label: 'Status', skeletonClassName: 'h-5 w-20' },
            {
              label: 'Pairs',
              headerClassName: 'text-right',
              cellClassName: 'text-right',
              skeletonClassName: 'h-4 w-8 ml-auto',
            },
            {
              label: 'Evaluations',
              headerClassName: 'text-right',
              cellClassName: 'text-right',
              skeletonClassName: 'h-4 w-8 ml-auto',
            },
            { label: 'Dataset', skeletonClassName: 'h-4 w-16' },
            {
              label: 'Created',
              headerClassName: 'text-right',
              cellClassName: 'text-right',
              skeletonClassName: 'h-4 w-28 ml-auto',
            },
          ]}
        />
      ) : isError ? (
        <div className="flex items-center justify-center gap-2.5 bg-destructive-soft px-4 py-12 text-sm font-semibold text-destructive">
          <Warning className="size-5 shrink-0" aria-hidden="true" />
          <span>Failed to load training jobs.</span>
        </div>
      ) : jobs.length === 0 ? (
        <div className="space-y-1.5 py-16 text-center text-text-muted">
          <Database className="mx-auto size-8 text-text-muted/40" aria-hidden="true" />
          <p className="text-sm font-semibold text-text">No training jobs yet.</p>
          <p className="mx-auto max-w-sm text-xs text-text-muted">
            Start a training job to freeze a dataset snapshot and get a download / upload URL
            pair for Colab.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className={TABLE_STYLES.table}>
            <thead className={TABLE_STYLES.thead}>
              <tr>
                <th className={TABLE_STYLES.th}>Job ID</th>
                <th className={TABLE_STYLES.th}>Status</th>
                <th className={cn(TABLE_STYLES.th, 'text-right')}>Pairs</th>
                <th className={cn(TABLE_STYLES.th, 'text-right')}>Evaluations</th>
                <th className={TABLE_STYLES.th}>Dataset</th>
                <th className={cn(TABLE_STYLES.th, 'text-right')}>Created</th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {jobs.map((job: TrainingJobItem) => (
                <tr key={job.job_id} className={TABLE_STYLES.tr}>
                  <td className={cn(TABLE_STYLES.tdData, 'font-mono text-xs text-text-muted')}>
                    <span
                      className="inline-block max-w-[16rem] truncate align-middle"
                      title={job.job_id}
                    >
                      {job.job_id}
                    </span>
                  </td>
                  <td className={TABLE_STYLES.td}>
                    <Badge variant={getJobStatusVariant(job.status)} withDot>
                      {capitalize(job.status)}
                    </Badge>
                  </td>
                  <td className={cn(TABLE_STYLES.tdData, 'text-right tabular-nums')}>
                    {job.pair_count ?? '—'}
                  </td>
                  <td className={cn(TABLE_STYLES.tdData, 'text-right tabular-nums')}>
                    {job.evaluation_count ?? '—'}
                  </td>
                  <td
                    className={cn(TABLE_STYLES.tdData, 'font-mono text-xs text-text-muted')}
                    title={job.pairs_sha256 ?? undefined}
                  >
                    {shortHash(job.pairs_sha256)}
                  </td>
                  <td className={cn(TABLE_STYLES.tdData, 'text-right text-text-muted')}>
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
