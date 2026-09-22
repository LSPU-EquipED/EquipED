import { Link } from '@tanstack/react-router';
import {
  Warning,
  CaretLeft,
  CaretRight,
  MagnifyingGlass,
  Books,
  CheckCircle,
  Clock,
  FileText,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import { Badge, Button, cn, TableSkeleton, Skeleton, BUTTON_STYLES, TABLE_STYLES } from '@equiped/ui';
import type { AlignmentLevel, AlignmentProcessingStatus } from '../types';
import { useSyllabusAlignmentList } from '../hooks/useSyllabusAlignmentList';

const levelLabels: Record<AlignmentLevel, string> = {
  MEETS: 'Meets',
  PARTIALLY_MEETS: 'Partially meets',
  DOES_NOT_MEET: 'Does not meet',
  UNAVAILABLE: 'Unavailable',
};

function statusLabel(status: AlignmentProcessingStatus, level?: AlignmentLevel | null) {
  if (status === 'COMPLETED' && level) return levelLabels[level];
  if (status === 'FAILED') return 'Unavailable';
  return status === 'QUEUED' ? 'Queued' : 'Running';
}

function getLevelBadgeVariant(status: AlignmentProcessingStatus, level?: AlignmentLevel | null) {
  if (status === 'COMPLETED') {
    if (level === 'MEETS') return 'success' as const;
    if (level === 'PARTIALLY_MEETS') return 'warning' as const;
    if (level === 'DOES_NOT_MEET') return 'destructive' as const;
  }
  if (status === 'FAILED') return 'destructive' as const;
  return 'neutral' as const;
}

export function SyllabusAlignmentPage() {
  const {
    page,
    setPage,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    slms,
    total,
    totalPages,
    items,
    metrics,
    filteredItems,
  } = useSyllabusAlignmentList(10);

  return (
    <section className="mx-auto max-w-[108rem] space-y-7 px-4 py-6 sm:px-7 sm:py-8">
      {/* 4-Cell Divided Metrics Strip */}
      <div
        className="grid grid-cols-2 divide-x divide-y divide-border overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-4 sm:divide-y-0 shadow-none"
        role="region"
        aria-label="Syllabus alignment overview metrics"
      >
        <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
          <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
            <span>Course Modules</span>
            <Books className="size-3.5 text-primary" aria-hidden="true" />
          </div>
          <div className="mt-2">
            {slms.isLoading && !slms.data ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              <>
                <span className="text-2xl font-semibold tabular-nums text-text">
                  {total}
                </span>
                <span className="ml-1.5 text-[11px] text-text-muted">on record</span>
              </>
            )}
          </div>
        </div>

        <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
          <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
            <span>Meets Syllabus</span>
            <CheckCircle className="size-3.5 text-success" aria-hidden="true" />
          </div>
          <div className="mt-2">
            {slms.isLoading && !slms.data ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              <>
                <span className="text-2xl font-semibold tabular-nums text-success">
                  {metrics.meets}
                </span>
                <span className="ml-1.5 text-[11px] text-text-muted">aligned</span>
              </>
            )}
          </div>
        </div>

        <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
          <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
            <span>Partially Meets</span>
            <Warning className="size-3.5 text-warning" aria-hidden="true" />
          </div>
          <div className="mt-2">
            {slms.isLoading && !slms.data ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              <>
                <span className="text-2xl font-semibold tabular-nums text-warning">
                  {metrics.partiallyMeets}
                </span>
                <span className="ml-1.5 text-[11px] text-text-muted">partial</span>
              </>
            )}
          </div>
        </div>

        <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
          <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
            <span>Needs Attention</span>
            <Clock className="size-3.5 text-destructive" aria-hidden="true" />
          </div>
          <div className="mt-2">
            {slms.isLoading && !slms.data ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              <>
                <span className="text-2xl font-semibold tabular-nums text-destructive">
                  {metrics.attention}
                </span>
                <span className="ml-1.5 text-[11px] text-text-muted">
                  {metrics.pending > 0 ? `+ ${metrics.pending} pending` : 'divergent'}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Loading state */}
      {slms.isLoading && !slms.data && (
        <TableSkeleton
          ariaLabel="Loading SLM syllabus alignment records"
          columns={[
            { label: 'SLM Document / Module', skeletonClassName: 'h-5 w-full max-w-72' },
            { label: 'Program / Course', skeletonClassName: 'h-4 w-36' },
            { label: 'Syllabus Alignment', skeletonClassName: 'h-5 w-32' },
            { label: 'Action', skeletonClassName: 'h-8 w-24 ml-auto' },
          ]}
          rows={8}
        />
      )}

      {/* Error state */}
      {slms.isError && (
        <div className="flex items-center gap-2 rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs font-semibold text-destructive" role="alert">
          <Warning className="size-4 shrink-0" aria-hidden="true" />
          <span>{getErrorMessage(slms.error, 'Unable to load SLM documents.')}</span>
        </div>
      )}

      {/* Empty state */}
      {!slms.isLoading && !slms.isError && items.length === 0 && (
        <div className="rounded-md border border-dashed border-border bg-surface p-12 text-center">
          <FileText className="mx-auto size-8 text-text-muted mb-2" aria-hidden="true" />
          <p className="font-semibold text-text">No SLM documents available</p>
          <p className="text-xs text-text-muted mt-1">Upload course learning modules in SLM Storage to begin syllabus alignment checks.</p>
        </div>
      )}

      {/* Unified Table Container */}
      {!slms.isLoading && !slms.isError && items.length > 0 && (
        <div className={TABLE_STYLES.wrapper}>
          {/* Table Search & Status Filter Tabs Toolbar */}
          <div className="flex flex-col gap-3 border-b border-border bg-surface px-4 sm:px-5 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              {/* Status Filter Tabs */}
              <div className="flex flex-wrap items-center gap-1">
                {(
                  [
                    ['ALL', `All (${items.length})`],
                    ['MEETS', `Meets (${metrics.meets})`],
                    ['PARTIALLY_MEETS', `Partially meets (${metrics.partiallyMeets})`],
                    ['ATTENTION', `Needs attention (${metrics.attention})`],
                    ['PENDING', `Pending (${metrics.pending})`],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setStatusFilter(key)}
                    className={cn(
                      'rounded-xs px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-ring',
                      statusFilter === key
                        ? 'bg-surface-subtle text-text border border-border shadow-2xs'
                        : 'text-text-muted hover:text-text hover:bg-surface-subtle/50',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <span className="text-xs text-text-muted tabular-nums">
                {filteredItems.length} of {total} modules shown
              </span>
            </div>

            <div className="relative w-full sm:max-w-md">
              <MagnifyingGlass
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted"
                aria-hidden="true"
              />
              <input
                type="text"
                placeholder="Search by SLM title, course, program, or syllabus…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8.5 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
                aria-label="Search syllabus alignments"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-[40%] min-w-[16rem]')}>
                    SLM Document / Module
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-[20%]')}>
                    Program / Course
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-[25%]')}>
                    Syllabus Alignment
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-[15%] text-right')}>
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {filteredItems.map((item) => (
                  <tr key={item.document_id} className={TABLE_STYLES.tr}>
                    <td className={TABLE_STYLES.td}>
                      <div className="flex flex-col">
                        <span className="font-semibold text-text line-clamp-1">{item.title}</span>
                        <span className="text-xs text-text-muted mt-0.5">
                          {item.lesson_title || item.course_title || 'No lesson title'}
                        </span>
                      </div>
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-text-muted text-xs')}>
                      {[item.program, item.course_code].filter(Boolean).join(' · ') ||
                        'Not specified'}
                    </td>
                    <td className={TABLE_STYLES.td}>
                      {item.current_result ? (
                        <div className="flex flex-col gap-0.5">
                          <Badge variant={getLevelBadgeVariant(item.current_result.status, item.current_result.alignment_level)} withDot>
                            {statusLabel(item.current_result.status, item.current_result.alignment_level)}
                          </Badge>
                          {item.current_result.syllabus_title ? (
                            <span className="text-[11px] text-text-muted truncate max-w-xs" title={item.current_result.syllabus_title}>
                              Ref: {item.current_result.syllabus_title}
                            </span>
                          ) : null}
                        </div>
                      ) : (
                        <span className="text-xs font-medium text-text-muted">
                          Not yet evaluated
                        </span>
                      )}
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-right')}>
                      {item.evaluation_available ? (
                        <div className="flex flex-wrap justify-end gap-2">
                          {item.current_result?.status === 'COMPLETED' ? (
                            <Link
                              to="/syllabus-alignment/$documentId"
                              params={{ documentId: item.document_id }}
                              className={cn(BUTTON_STYLES.base, BUTTON_STYLES.variants.secondary, BUTTON_STYLES.sizes.sm, 'text-xs h-7.5 px-3')}
                            >
                              <span>View Result</span>
                              <CaretRight className="size-3" aria-hidden="true" />
                            </Link>
                          ) : ['QUEUED', 'RUNNING'].includes(item.current_result?.status ?? '') ? (
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              disabled
                              isLoading
                              className="text-xs h-7.5 px-3"
                            >
                              Running
                            </Button>
                          ) : (
                            <Link
                              to="/syllabus-alignment/$documentId"
                              params={{ documentId: item.document_id }}
                              className={cn(BUTTON_STYLES.base, BUTTON_STYLES.variants.primary, BUTTON_STYLES.sizes.sm, 'text-xs h-7.5 px-3')}
                            >
                              <span>{item.current_result?.status === 'FAILED' ? 'Retry' : 'Evaluate'}</span>
                              <CaretRight className="size-3" aria-hidden="true" />
                            </Link>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs font-medium text-text-muted">
                          Processing unavailable
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <footer className="flex items-center justify-between border-t border-border bg-surface-subtle px-4 sm:px-6 py-2.5 text-xs text-text-muted">
              <span className="tabular-nums font-medium">
                Page {page} of {totalPages} · {total} SLM documents
              </span>
              <div className="flex gap-1.5">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  disabled={page === 1 || slms.isFetching}
                  className="h-7 px-2 text-xs"
                >
                  <CaretLeft className="size-3" aria-hidden="true" />
                  <span>Previous</span>
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  disabled={page === totalPages || slms.isFetching}
                  className="h-7 px-2 text-xs"
                >
                  <span>Next</span>
                  <CaretRight className="size-3" aria-hidden="true" />
                </Button>
              </div>
            </footer>
          )}
        </div>
      )}
    </section>
  );
}
