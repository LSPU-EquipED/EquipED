import { useState } from 'react';
import { ClipboardText, Warning } from '@phosphor-icons/react';
import { Skeleton, TableSkeleton, TABLE_STYLES, cn } from '@equiped/ui';
import type { HistoryEvaluationItem } from '../types';
import { HistoryEvaluationRow } from './HistoryEvaluationRow';

interface HistoryRowsProps {
  items: HistoryEvaluationItem[];
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  hasData: boolean;
  hasActiveFilters: boolean;
  onResetFilters: () => void;
}

export function HistoryRows({
  items,
  isLoading,
  isFetching,
  isError,
  hasData,
  hasActiveFilters,
  onResetFilters,
}: HistoryRowsProps) {
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const toggleRow = (id: string) => {
    setExpandedRowId((previous) => (previous === id ? null : id));
  };

  if (isLoading && !hasData) {
    return (
      <TableSkeleton
        ariaLabel="Loading evaluation history"
        tableClassName="table-fixed"
        columns={[
          {
            label: 'Module',
            headerClassName: 'sm:pl-6',
            cellClassName: 'sm:pl-6',
            skeletonClassName: 'h-4 w-full max-w-48',
          },
          {
            label: 'Status',
            headerClassName: 'hidden w-36 lg:table-cell',
            cellClassName: 'hidden lg:table-cell',
            skeletonClassName: 'h-5 w-24',
          },
          {
            label: 'Submitted',
            headerClassName: 'hidden w-40 lg:table-cell',
            cellClassName: 'hidden lg:table-cell',
            skeletonClassName: 'h-4 w-28',
          },
          {
            label: 'Action',
            headerClassName: 'w-28 text-right sm:w-36 sm:pr-6',
            cellClassName: 'sm:pr-6',
            skeletonClassName: 'ml-auto h-10 w-full max-w-24',
          },
        ]}
      />
    );
  }

  if (isError) {
    return (
      <div
        className="flex min-h-44 flex-col items-center justify-center gap-2 border-b border-border bg-destructive-soft/35 px-6 py-12 text-center"
        role="alert"
      >
        <Warning className="size-6 text-destructive" aria-hidden="true" />
        <p className="text-sm font-semibold text-text">
          Failed to load evaluation history.
        </p>
        <p className="max-w-sm text-xs text-text-muted">
          Refresh the page or try again in a moment.
        </p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="px-6 py-16 text-center text-sm text-text-muted">
        {isFetching ? (
          <div
            className="space-y-3 px-6 py-5"
            role="status"
            aria-label="Loading evaluation history"
          >
            <Skeleton className="mx-auto h-3 w-40" />
            <Skeleton className="mx-auto h-3 w-64 max-w-full" />
            <Skeleton className="mx-auto h-8 w-28" />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-2">
            <ClipboardText
              className="size-6 text-text-muted/60"
              aria-hidden="true"
            />
            <p className="font-semibold text-text">
              {hasActiveFilters
                ? 'No evaluations match your filters'
                : 'No evaluations yet'}
            </p>
            <p className="max-w-sm text-xs text-text-muted">
              {hasActiveFilters
                ? 'Try another title on this page, or reset the filters.'
                : 'Evaluations will appear here once you run one from a specialist workspace.'}
            </p>
            {hasActiveFilters ? (
              <button
                type="button"
                onClick={onResetFilters}
                className="mt-2 cursor-pointer text-xs font-semibold text-primary hover:underline"
              >
                Reset filters
              </button>
            ) : null}
          </div>
        )}
      </div>
    );
  }

  return (
    <table
      className={cn(
        TABLE_STYLES.table,
        'table-fixed',
        isFetching && 'opacity-60 transition-opacity',
      )}
    >
      <caption className="sr-only">Evaluation history records</caption>
      <thead className={TABLE_STYLES.thead}>
        <tr>
          <th scope="col" className={cn(TABLE_STYLES.th, 'sm:pl-6')}>
            Module
          </th>
          <th
            scope="col"
            className={cn(TABLE_STYLES.th, 'hidden w-36 lg:table-cell')}
          >
            Status
          </th>
          <th
            scope="col"
            className={cn(TABLE_STYLES.th, 'hidden w-40 lg:table-cell')}
          >
            Submitted
          </th>
          <th
            scope="col"
            className={cn(TABLE_STYLES.th, 'w-28 text-right sm:w-36 sm:pr-6')}
          >
            Action
          </th>
        </tr>
      </thead>
      <tbody className={TABLE_STYLES.tbody}>
        {items.map((record) => (
          <HistoryEvaluationRow
            key={record.evaluation_id}
            record={record}
            isExpanded={expandedRowId === record.evaluation_id}
            copiedId={copiedId}
            onToggle={toggleRow}
            onCopyId={handleCopy}
          />
        ))}
      </tbody>
    </table>
  );
}
