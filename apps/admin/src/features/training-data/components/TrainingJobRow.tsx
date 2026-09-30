import { useId, useState } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { Badge, Button, CollapsibleRow, TABLE_STYLES, cn } from '@equiped/ui';
import type { StatusVariant } from '@equiped/ui';
import type { TrainingJobItem } from '../types';

const JOB_STATUS: Record<TrainingJobItem['status'], { label: string; variant: StatusVariant }> = {
  pending: { label: 'Prepared', variant: 'neutral' },
  downloaded: { label: 'Downloaded', variant: 'info' },
  completed: { label: 'Adapter received', variant: 'info' },
};

export function TrainingJobRow({ job }: { job: TrainingJobItem }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const status = JOB_STATUS[job.status];
  const created = new Date(job.created_at);

  return (
    <>
      <tr className={TABLE_STYLES.tr}>
        <td className={TABLE_STYLES.tdData}>
          <time dateTime={job.created_at} className="block font-medium">
            {created.toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </time>
          <span className="text-sm text-text-muted">
            {created.toLocaleTimeString(undefined, {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </td>
        <td className={TABLE_STYLES.tdData}>
          <span className="block font-medium">{job.pair_count ?? '—'} pairs</span>
          <span className="text-sm text-text-muted">{job.evaluation_count ?? '—'} evaluations</span>
        </td>
        <td className={TABLE_STYLES.td}>
          <Badge variant={status.variant} className="whitespace-normal tracking-normal">
            {status.label}
          </Badge>
        </td>
        <td className="pr-3 text-right">
          <Button
            variant="ghost"
            size="icon"
            title={expanded ? 'Hide details' : 'Show details'}
            aria-label={`${expanded ? 'Hide' : 'Show'} details for run ${job.job_id}`}
            aria-expanded={expanded}
            aria-controls={detailsId}
            onClick={() => setExpanded(!expanded)}
          >
            <CaretDown
              className={cn(
                'size-4 transition-transform duration-180 motion-reduce:transition-none',
                expanded && 'rotate-180',
              )}
              aria-hidden="true"
            />
          </Button>
        </td>
      </tr>
      <CollapsibleRow id={detailsId} isExpanded={expanded} colSpan={4} innerClassName="p-4 sm:p-5">
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          {[
            ['Run ID', job.job_id],
            ['Dataset SHA-256', job.pairs_sha256 ?? 'Not recorded'],
            ['Reviewers', job.reviewer_count ?? 'Not recorded'],
            [
              'Snapshot created',
              job.export_timestamp
                ? new Date(job.export_timestamp).toLocaleString()
                : 'Not recorded',
            ],
          ].map(([label, value]) => (
            <div key={label} className="min-w-0 space-y-1">
              <dt className="text-text-muted">{label}</dt>
              <dd className="break-words font-medium tabular-nums text-text [overflow-wrap:anywhere]">
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </CollapsibleRow>
    </>
  );
}
