import { CaretDown } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import {
  Badge,
  CollapsibleRow,
  TABLE_STYLES,
  BUTTON_STYLES,
  cn,
} from '@equiped/ui';
import type { HistoryEvaluationItem } from '../types';
import { formatStatus, getStatusVariant } from '../utils/historyFormatters';
import { HistorySubmittedDate } from './HistorySubmittedDate';
import { HistoryRunDetails } from './HistoryRunDetails';

interface HistoryEvaluationRowProps {
  record: HistoryEvaluationItem;
  isExpanded: boolean;
  copiedId: string | null;
  onToggle: (id: string) => void;
  onCopyId: (id: string) => void;
}

export function HistoryEvaluationRow({
  record,
  isExpanded,
  copiedId,
  onToggle,
  onCopyId,
}: HistoryEvaluationRowProps) {
  const isCompleted = record.status.toUpperCase().startsWith('COMPLETED');
  const actionLabel = isCompleted
    ? 'View results'
    : getStatusVariant(record.status) === 'destructive'
      ? 'View details'
      : 'View progress';

  return (
    <>
      <tr className={cn(TABLE_STYLES.tr, isExpanded && 'bg-surface-subtle/30')}>
        <td
          className={cn(TABLE_STYLES.td, 'align-top sm:pl-6 lg:align-middle')}
        >
          <div className="flex items-start gap-2 lg:items-center">
            <button
              type="button"
              onClick={() => onToggle(record.evaluation_id)}
              aria-expanded={isExpanded}
              aria-controls={`history-details-${record.evaluation_id}`}
              aria-label={
                isExpanded
                  ? `Collapse details for ${record.document_title || record.evaluation_id}`
                  : `Expand details for ${record.document_title || record.evaluation_id}`
              }
              className="-ml-2 inline-flex size-10 shrink-0 items-center justify-center rounded-sm text-text-muted transition-colors hover:bg-surface-subtle hover:text-text focus-visible:outline-2 focus-visible:outline-ring"
            >
              <CaretDown
                className={cn(
                  'size-3.5 transition-transform duration-150 motion-reduce:transition-none',
                  isExpanded ? 'rotate-180' : '-rotate-90',
                )}
                aria-hidden="true"
              />
            </button>
            <div className="min-w-0 pt-2 lg:py-0">
              <span className="block break-words font-medium leading-relaxed text-text [overflow-wrap:anywhere]">
                {record.document_title ?? '—'}
              </span>
              <div className="mt-2 space-y-2 lg:hidden">
                <Badge
                  className="tracking-normal"
                  variant={getStatusVariant(record.status)}
                >
                  {formatStatus(record.status)}
                </Badge>
                  <HistorySubmittedDate value={record.submitted_at} compact />
              </div>
            </div>
          </div>
        </td>
        <td
          className={cn(TABLE_STYLES.td, 'hidden align-middle lg:table-cell')}
        >
          <Badge
            className="max-w-full whitespace-normal tracking-normal"
            variant={getStatusVariant(record.status)}
          >
            {formatStatus(record.status)}
          </Badge>
        </td>
        <td
          className={cn(
            TABLE_STYLES.tdData,
            'hidden align-middle lg:table-cell',
          )}
        >
          <HistorySubmittedDate value={record.submitted_at} />
        </td>
        <td
          className={cn(
            TABLE_STYLES.td,
            'text-right align-top sm:pr-6 lg:align-middle',
          )}
        >
          <Link
            to="/evaluations/$id"
            params={{ id: record.evaluation_id }}
            aria-label={`${isCompleted ? 'View evaluation results' : actionLabel} for ${record.document_title || record.evaluation_id}`}
            className={cn(
              BUTTON_STYLES.base,
              'h-10 whitespace-nowrap px-1 text-xs text-primary hover:bg-surface-subtle',
            )}
          >
            {actionLabel}
          </Link>
        </td>
      </tr>

      <CollapsibleRow
        id={`history-details-${record.evaluation_id}`}
        isExpanded={isExpanded}
        colSpan={4}
        className="bg-surface-subtle/40"
        innerClassName="px-4 py-5 sm:px-6"
      >
        <HistoryRunDetails
          record={record}
          copiedId={copiedId}
          onCopyId={onCopyId}
        />
      </CollapsibleRow>
    </>
  );
}
