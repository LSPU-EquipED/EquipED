import { useId, useState } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { Badge, Button, CollapsibleRow, TABLE_STYLES, TYPOGRAPHY, cn } from '@equiped/ui';
import type { StatusVariant } from '@equiped/ui';
import type { TrainingJobItem } from '../types';
import { TrainingRecordMetadata } from './TrainingRecordMetadata';

const JOB_STATUS: Record<TrainingJobItem['status'], { label: string; variant: StatusVariant }> = {
  pending: { label: 'Waiting to start', variant: 'neutral' },
  downloaded: { label: 'In progress', variant: 'info' },
  completed: { label: 'Finished', variant: 'info' },
};

export function TrainingJobRow({ job }: { job: TrainingJobItem }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const status = JOB_STATUS[job.status];
  const created = new Date(job.created_at);

  return (
    <>
      <tr className={TABLE_STYLES.tr}>
        <td className={cn(TYPOGRAPHY.dataMd, 'px-4 py-2')}>
          <time dateTime={job.created_at} className="block font-medium">
            {created.toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </time>
        </td>
        <td className={cn(TYPOGRAPHY.dataMd, 'px-4 py-2')}>
          <span className="block font-medium">{job.pair_count ?? '—'} examples</span>
          <span className="block text-xs leading-4 text-text-muted">
            {job.evaluation_count ?? '—'} evaluations
          </span>
        </td>
        <td className="px-4 py-2">
          <Badge variant={status.variant} className="whitespace-normal tracking-normal">
            {status.label}
          </Badge>
        </td>
        <td className="px-3 py-2 text-right">
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
      <CollapsibleRow id={detailsId} isExpanded={expanded} colSpan={4} innerClassName="px-4 py-3">
        <TrainingRecordMetadata
          tabularValues
          entries={[
            ['Started', created.toLocaleString()],
            ['Reviewers', job.reviewer_count ?? 'Not recorded'],
          ]}
        />
        <details className="mt-3 border-t border-border pt-3 text-sm text-text-muted">
          <summary className="cursor-pointer text-[13px] font-medium text-text">
            For IT staff
          </summary>
          <div className="mt-3">
            <TrainingRecordMetadata
              tabularValues
              entries={[
                ['Run ID', job.job_id],
                ['Examples SHA-256', job.pairs_sha256 ?? 'Not recorded'],
                [
                  'Examples exported',
                  job.export_timestamp
                    ? new Date(job.export_timestamp).toLocaleString()
                    : 'Not recorded',
                ],
              ]}
            />
          </div>
        </details>
      </CollapsibleRow>
    </>
  );
}
