import { Fragment, useState } from 'react';
import { CaretDown, ClipboardText, Warning } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import { TARGET_AGENT_META, isTargetAgent } from '@equiped/types';
import {
  Badge,
  Skeleton,
  TableSkeleton,
  TABLE_STYLES,
  BUTTON_STYLES,
  cn,
} from '@equiped/ui';
import type { HistoryEvaluationItem } from '../types';
import {
  formatDate,
  formatDuration,
  formatStatus,
  getStatusVariant,
} from '../utils/historyFormatters';

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
        columns={[
          { label: 'Module', skeletonClassName: 'h-4 w-48' },
          { label: 'Status', skeletonClassName: 'h-5 w-24' },
          { label: 'Submitted', skeletonClassName: 'h-4 w-28' },
          {
            label: 'Action',
            headerClassName: 'text-right',
            skeletonClassName: 'ml-auto h-7 w-24',
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
        isFetching && 'opacity-60 transition-opacity',
      )}
    >
      <thead className={TABLE_STYLES.thead}>
        <tr>
          <th scope="col" className={TABLE_STYLES.th}>
            Module
          </th>
          <th scope="col" className={TABLE_STYLES.th}>
            Status
          </th>
          <th scope="col" className={TABLE_STYLES.th}>
            Submitted
          </th>
          <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
            Action
          </th>
        </tr>
      </thead>
      <tbody className={TABLE_STYLES.tbody}>
        {items.map((record) => {
          const isExpanded = expandedRowId === record.evaluation_id;
          const duration = formatDuration(
            record.duration_seconds,
            record.submitted_at,
            record.completed_at,
          );
          const isCompleted = record.status
            .toUpperCase()
            .startsWith('COMPLETED');
          const actionLabel = isCompleted
            ? 'View results'
            : getStatusVariant(record.status) === 'destructive'
              ? 'View details'
              : 'View progress';

          return (
            <Fragment key={record.evaluation_id}>
              <tr
                className={cn(
                  TABLE_STYLES.tr,
                  isExpanded && 'bg-surface-subtle/30',
                )}
              >
                <td className={cn(TABLE_STYLES.td, 'min-w-[14rem]')}>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => toggleRow(record.evaluation_id)}
                      aria-expanded={isExpanded}
                      aria-label={
                        isExpanded
                          ? `Collapse details for ${record.document_title || record.evaluation_id}`
                          : `Expand details for ${record.document_title || record.evaluation_id}`
                      }
                      className="inline-flex size-8 shrink-0 items-center justify-center rounded-xs text-text-muted transition-colors hover:bg-surface-subtle hover:text-text focus-visible:outline-2 focus-visible:outline-ring"
                    >
                      <CaretDown
                        className={cn(
                          'size-3.5 transition-transform duration-150 motion-reduce:transition-none',
                          isExpanded ? 'rotate-180' : '-rotate-90',
                        )}
                        aria-hidden="true"
                      />
                    </button>
                    <span className="max-w-xl break-words font-medium text-text [overflow-wrap:anywhere]">
                      {record.document_title ?? '—'}
                    </span>
                  </div>
                </td>
                <td className={TABLE_STYLES.td}>
                  <Badge variant={getStatusVariant(record.status)}>
                    {formatStatus(record.status)}
                  </Badge>
                </td>
                <td
                  className={cn(
                    TABLE_STYLES.tdData,
                    'whitespace-nowrap text-xs text-text-muted tabular-nums',
                  )}
                >
                  <time dateTime={record.submitted_at}>
                    {formatDate(record.submitted_at)}
                  </time>
                </td>
                <td className={cn(TABLE_STYLES.td, 'text-right')}>
                  <Link
                    to="/evaluations/$id"
                    params={{ id: record.evaluation_id }}
                    aria-label={`${isCompleted ? 'View evaluation results' : actionLabel} for ${record.document_title || record.evaluation_id}`}
                    className={cn(
                      BUTTON_STYLES.base,
                      BUTTON_STYLES.variants.secondary,
                      BUTTON_STYLES.sizes.sm,
                      'h-8 px-2.5 text-xs',
                    )}
                  >
                    {actionLabel}
                  </Link>
                </td>
              </tr>

              {isExpanded && (
                <tr className="border-b border-border bg-surface-subtle/25">
                  <td colSpan={4} className="px-4 py-5 sm:px-6">
                    <div className="space-y-4 text-xs">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <span className="font-semibold text-text">
                          Run details
                        </span>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                          <Link
                            to="/documents"
                            className="font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                          >
                            Module Library
                          </Link>
                          {isTargetAgent(record.target_agent) && (
                            <Link
                              to="/specialists/$agentId/$documentId"
                              params={{
                                agentId: record.target_agent,
                                documentId: record.document_id,
                              }}
                              className="font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                            >
                              {
                                TARGET_AGENT_META[record.target_agent]
                                  .shortLabel
                              }{' '}
                              workspace
                            </Link>
                          )}
                        </div>
                      </div>
                      <dl className="grid min-w-0 gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-3">
                        <div className="min-w-0 sm:col-span-2 xl:col-span-1">
                          <dt className="text-text-muted">Evaluation ID</dt>
                          <dd className="m-0 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span className="break-all font-mono text-xs text-text">
                              {record.evaluation_id}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleCopy(record.evaluation_id)}
                              aria-label="Copy full evaluation ID"
                              className="inline-flex min-h-8 items-center font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                            >
                              {copiedId === record.evaluation_id
                                ? 'Copied'
                                : 'Copy ID'}
                            </button>
                          </dd>
                        </div>
                        <div className="min-w-0">
                          <dt className="text-text-muted">Specialist</dt>
                          <dd className="m-0 mt-1 text-text">
                            {isTargetAgent(record.target_agent)
                              ? TARGET_AGENT_META[record.target_agent].fullName
                              : record.target_agent === 'all'
                                ? 'All domains'
                                : (record.target_agent ?? '—')}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-text-muted">Completed</dt>
                          <dd className="m-0 mt-1 text-text tabular-nums">
                            {record.completed_at ? (
                              <time dateTime={record.completed_at}>
                                {formatDate(record.completed_at)}
                              </time>
                            ) : (
                              '—'
                            )}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-text-muted">Duration</dt>
                          <dd className="m-0 mt-1 text-text tabular-nums">
                            {duration ?? '—'}
                          </dd>
                        </div>
                        <div className="min-w-0">
                          <dt className="text-text-muted">Document ID</dt>
                          <dd className="m-0 mt-1 break-all font-mono text-xs text-text">
                            {record.document_id}
                          </dd>
                        </div>
                        {record.syllabus_id && (
                          <div className="min-w-0">
                            <dt className="text-text-muted">
                              Syllabus reference
                            </dt>
                            <dd className="m-0 mt-1 break-all font-mono text-xs text-text">
                              {record.syllabus_id}
                            </dd>
                          </div>
                        )}
                        {record.curriculum_id && (
                          <div className="min-w-0">
                            <dt className="text-text-muted">
                              Curriculum reference
                            </dt>
                            <dd className="m-0 mt-1 break-all font-mono text-xs text-text">
                              {record.curriculum_id}
                            </dd>
                          </div>
                        )}
                        {record.submitted_by && (
                          <div className="min-w-0">
                            <dt className="text-text-muted">Submitted by</dt>
                            <dd className="m-0 mt-1 break-words text-text">
                              {record.submitted_by}
                            </dd>
                          </div>
                        )}
                      </dl>

                      {record.error_message && (
                        <div className="flex items-center gap-2 rounded-xs border border-destructive/30 bg-destructive-soft p-2.5 text-xs text-destructive">
                          <Warning
                            className="size-4 shrink-0"
                            aria-hidden="true"
                          />
                          <span>{record.error_message}</span>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
