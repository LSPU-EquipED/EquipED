import { useEffect, useState } from 'react';
import { Check, Clock, Copy, Database, Rocket, Warning } from '@phosphor-icons/react';
import { Badge, Button, CARD_STYLES, TABLE_STYLES, TableSkeleton, cn } from '@equiped/ui';
import type { StatusVariant } from '@equiped/ui';
import { useStartTrainingJob } from '../hooks/useStartTrainingJob';
import { useTrainingJobs } from '../hooks/useTrainingJobs';
import type { TrainingJobCreateResponse, TrainingJobItem } from '../types';

function getJobStatusVariant(status: string): StatusVariant {
  if (status === 'completed') return 'success';
  if (status === 'downloaded') return 'info';
  return 'neutral';
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatCountdown(expiresAtIso: string, now: number): string {
  const diffMs = new Date(expiresAtIso).getTime() - now;
  if (diffMs <= 0) return 'Expired';
  const totalMinutes = Math.floor(diffMs / 60_000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h remaining`;
  if (hours > 0) return `${hours}h ${minutes}m remaining`;
  return `${minutes}m remaining`;
}

function CredentialField({
  label,
  url,
  expiresAt,
  now,
}: {
  label: string;
  url: string;
  expiresAt: string;
  now: number;
}) {
  const [copied, setCopied] = useState(false);
  const expired = new Date(expiresAt).getTime() <= now;

  const handleCopy = () => {
    void navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-text">{label}</span>
        <span
          className={cn(
            'inline-flex items-center gap-1 text-[11px] font-semibold tabular-nums',
            expired ? 'text-destructive' : 'text-text-muted',
          )}
        >
          <Clock className="size-3" aria-hidden="true" />
          {formatCountdown(expiresAt, now)}
        </span>
      </div>
      <div className="flex items-stretch gap-2">
        <code className="min-w-0 flex-1 truncate rounded-sm border border-input bg-surface px-3 py-2 font-mono text-xs text-text">
          {url}
        </code>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-semibold text-primary transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {copied ? (
            <>
              <Check className="size-3.5 text-success" aria-hidden="true" />
              <span className="text-success">Copied</span>
            </>
          ) : (
            <>
              <Copy className="size-3.5" aria-hidden="true" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export function TrainingJobsPanel({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useTrainingJobs(agentId);
  const startJob = useStartTrainingJob(agentId);
  const [lastCreated, setLastCreated] = useState<TrainingJobCreateResponse | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!lastCreated) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [lastCreated]);

  const handleStart = () => {
    setLastCreated(null);
    startJob.mutate(undefined, {
      onSuccess: (result) => {
        setLastCreated(result);
        setNow(Date.now());
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

      {lastCreated ? (
        <div className="space-y-4 border-b border-border bg-surface-subtle p-4 sm:p-5">
          <p className="text-xs font-semibold text-text-muted">
            Paste these into your Colab notebook now — each is shown only once.
          </p>
          <CredentialField
            label="Download URL (notebook cell 1)"
            url={lastCreated.download_url}
            expiresAt={lastCreated.download_expires_at}
            now={now}
          />
          <CredentialField
            label="Upload URL (notebook final cell)"
            url={lastCreated.upload_url}
            expiresAt={lastCreated.upload_expires_at}
            now={now}
          />
        </div>
      ) : null}

      {isLoading ? (
        <TableSkeleton
          ariaLabel="Loading training jobs"
          columns={[
            { label: 'Job ID', skeletonClassName: 'h-4 w-40' },
            { label: 'Status', skeletonClassName: 'h-5 w-20' },
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
