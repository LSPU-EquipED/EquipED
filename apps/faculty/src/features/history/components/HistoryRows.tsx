import { Fragment, useState } from 'react';
import {
  ArrowSquareOut,
  CaretDown,
  Check,
  ClipboardText,
  Clock,
  Copy,
  FileText,
  FolderOpen,
  Warning,
} from '@phosphor-icons/react';
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
  formatRelativeTime,
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
          { label: 'Document / SLM', headerClassName: 'min-w-[18rem]', cellClassName: 'min-w-[18rem]', skeletonClassName: 'h-4 w-56' },
          { label: 'Role', skeletonClassName: 'h-5 w-16' },
          { label: 'Status', skeletonClassName: 'h-5 w-24' },
          { label: 'Submitted', skeletonClassName: 'h-4 w-28' },
          { label: 'Completed', skeletonClassName: 'h-4 w-28' },
          { label: 'Action', headerClassName: 'text-right', skeletonClassName: 'ml-auto h-7 w-24' },
        ]}
      />
    );
  }

  if (isError) {
    return (
      <div className="flex min-h-44 flex-col items-center justify-center gap-2 border-b border-border bg-destructive-soft/35 px-6 py-12 text-center" role="alert">
        <Warning className="size-6 text-destructive" aria-hidden="true" />
        <p className="text-sm font-semibold text-text">Failed to load evaluation history.</p>
        <p className="max-w-sm text-xs text-text-muted">Refresh the page or try again in a moment.</p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="px-6 py-16 text-center text-sm text-text-muted">
        {isFetching ? (
          <div className="space-y-3 px-6 py-5" role="status" aria-label="Loading evaluation history">
            <Skeleton className="mx-auto h-3 w-40" />
            <Skeleton className="mx-auto h-3 w-64 max-w-full" />
            <Skeleton className="mx-auto h-8 w-28" />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-2">
            <ClipboardText className="size-6 text-text-muted/60" aria-hidden="true" />
            <p className="font-semibold text-text">
              {hasActiveFilters ? 'No evaluations match your filters' : 'No evaluations yet'}
            </p>
            <p className="max-w-sm text-xs text-text-muted">
              {hasActiveFilters
                ? 'Try another title on this page, or reset the filters.'
                : 'Evaluations will appear here once you run one from SLM Storage or the specialist workspaces.'}
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
    <table className={cn(TABLE_STYLES.table, isFetching && 'opacity-60 transition-opacity')}>
      <thead className={TABLE_STYLES.thead}>
        <tr>
          <th scope="col" className={cn(TABLE_STYLES.th, 'w-8 px-2')}>
            <span className="sr-only">Expand</span>
          </th>
          <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[18rem]')}>Document / SLM</th>
          <th scope="col" className={TABLE_STYLES.th}>Role</th>
          <th scope="col" className={TABLE_STYLES.th}>Status</th>
          <th scope="col" className={TABLE_STYLES.th}>Submitted</th>
          <th scope="col" className={TABLE_STYLES.th}>Completed</th>
          <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>Action</th>
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
          const relativeSubmitted = formatRelativeTime(record.submitted_at);

          return (
            <Fragment key={record.evaluation_id}>
              <tr className={cn(TABLE_STYLES.tr, isExpanded && 'bg-surface-subtle/30')}>
                <td className="w-8 px-2 text-center align-middle">
                  <button
                    type="button"
                    onClick={() => toggleRow(record.evaluation_id)}
                    aria-expanded={isExpanded}
                    aria-label={
                      isExpanded
                        ? `Collapse details for ${record.document_title || record.evaluation_id}`
                        : `Expand details for ${record.document_title || record.evaluation_id}`
                    }
                    className="inline-flex size-6 items-center justify-center rounded-xs text-text-muted transition-colors hover:bg-surface-subtle hover:text-text focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    <CaretDown
                      className={cn(
                        'size-3.5 transition-transform duration-150',
                        isExpanded ? 'rotate-180' : '-rotate-90',
                      )}
                      aria-hidden="true"
                    />
                  </button>
                </td>
                <td className={TABLE_STYLES.td}>
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-sm border border-border bg-surface-subtle text-primary">
                      <FileText className="size-3.5" aria-hidden="true" />
                    </span>
                    <span className="flex min-w-0 flex-col">
                      <span className="line-clamp-1 font-semibold text-text">
                        {record.document_title ?? '—'}
                      </span>
                      <span className="mt-0.5 flex items-center gap-1.5 font-mono text-[10px] text-text-muted">
                        <span>ID: {record.evaluation_id.slice(0, 18)}...</span>
                        <button
                          type="button"
                          onClick={() => handleCopy(record.evaluation_id)}
                          title="Copy full evaluation ID"
                          aria-label="Copy full evaluation ID"
                          className="text-text-muted hover:text-text transition-colors p-0.5"
                        >
                          {copiedId === record.evaluation_id ? (
                            <Check className="size-3 text-success" aria-hidden="true" />
                          ) : (
                            <Copy className="size-3" aria-hidden="true" />
                          )}
                        </button>
                      </span>
                    </span>
                  </div>
                </td>
                <td className={TABLE_STYLES.td}>
                  {isTargetAgent(record.target_agent) ? (
                    <Badge variant="info">
                      {TARGET_AGENT_META[record.target_agent].shortLabel}
                    </Badge>
                  ) : (
                    <Badge variant="neutral">
                      {record.target_agent === 'all'
                        ? 'All Domains'
                        : record.target_agent ?? '—'}
                    </Badge>
                  )}
                </td>
                <td className={TABLE_STYLES.td}>
                  <div className="flex flex-col items-start gap-1">
                    <Badge variant={getStatusVariant(record.status)} withDot>
                      {record.status.replace('_', ' ')}
                    </Badge>
                    {duration ? (
                      <span className="inline-flex items-center gap-1 font-mono text-[10px] text-text-muted">
                        <Clock className="size-2.5" aria-hidden="true" />
                        {duration}
                      </span>
                    ) : null}
                  </div>
                </td>
                <td className={cn(TABLE_STYLES.tdData, 'text-xs text-text-muted tabular-nums')}>
                  <div className="flex flex-col">
                    <span>{formatDate(record.submitted_at)}</span>
                    {relativeSubmitted && (
                      <span className="text-[10px] text-text-muted/70">{relativeSubmitted}</span>
                    )}
                  </div>
                </td>
                <td className={cn(TABLE_STYLES.tdData, 'text-xs text-text-muted tabular-nums')}>
                  {record.completed_at ? (
                    <span>{formatDate(record.completed_at)}</span>
                  ) : (
                    <span className="italic text-text-muted">In progress…</span>
                  )}
                </td>
                <td className={cn(TABLE_STYLES.td, 'text-right')}>
                  <Link
                    to="/evaluations/$id"
                    params={{ id: record.evaluation_id }}
                    aria-label={`View audit scorecard for ${record.document_title || record.evaluation_id}`}
                    className={cn(
                      BUTTON_STYLES.base,
                      BUTTON_STYLES.variants.secondary,
                      BUTTON_STYLES.sizes.sm,
                      'h-8 px-2.5 text-xs',
                    )}
                  >
                    Scorecard
                  </Link>
                </td>
              </tr>

              {/* Expandable Inline Audit Dossier */}
              {isExpanded && (
                <tr className="bg-surface-subtle/25 border-b border-border">
                  <td colSpan={7} className="p-4 sm:p-5">
                    <div className="rounded-sm border border-border bg-surface p-4 text-xs space-y-3 shadow-none">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-text">Audit Trace Snapshot</span>
                          <span className="font-mono text-[10px] text-text-muted">
                            UUID: {record.evaluation_id}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <Link
                            to="/documents"
                            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                          >
                            <FolderOpen className="size-3.5" aria-hidden="true" />
                            <span>SLM Storage</span>
                            <ArrowSquareOut className="size-3" aria-hidden="true" />
                          </Link>
                          {isTargetAgent(record.target_agent) && (
                            <Link
                              to="/specialists/$agentId/$documentId"
                              params={{
                                agentId: record.target_agent,
                                documentId: record.document_id,
                              }}
                              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                            >
                              <span>
                                {TARGET_AGENT_META[record.target_agent].shortLabel} Desk
                              </span>
                              <ArrowSquareOut className="size-3" aria-hidden="true" />
                            </Link>
                          )}
                        </div>
                      </div>

                      <dl className="grid gap-x-6 gap-y-2.5 sm:grid-cols-2 lg:grid-cols-4 text-xs">
                        <div>
                          <dt className="text-text-muted">Document ID</dt>
                          <dd className="m-0 mt-0.5 font-mono text-[11px] text-text break-all">
                            {record.document_id}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-text-muted">Execution Timing</dt>
                          <dd className="m-0 mt-0.5 text-text">
                            {duration ? `${duration} total execution` : 'Timing pending'}
                          </dd>
                        </div>
                        {record.syllabus_id && (
                          <div>
                            <dt className="text-text-muted">Syllabus Reference</dt>
                            <dd className="m-0 mt-0.5 font-mono text-[11px] text-text break-all">
                              {record.syllabus_id}
                            </dd>
                          </div>
                        )}
                        {record.curriculum_id && (
                          <div>
                            <dt className="text-text-muted">Curriculum Reference</dt>
                            <dd className="m-0 mt-0.5 font-mono text-[11px] text-text break-all">
                              {record.curriculum_id}
                            </dd>
                          </div>
                        )}
                        {record.submitted_by && (
                          <div>
                            <dt className="text-text-muted">Submitted By</dt>
                            <dd className="m-0 mt-0.5 text-text">{record.submitted_by}</dd>
                          </div>
                        )}
                      </dl>

                      {record.error_message && (
                        <div className="flex items-center gap-2 rounded-xs border border-destructive/30 bg-destructive-soft p-2.5 text-xs text-destructive">
                          <Warning className="size-4 shrink-0" aria-hidden="true" />
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
