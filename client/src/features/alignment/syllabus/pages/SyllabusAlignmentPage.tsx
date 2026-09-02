import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import {
  Warning,
  CaretLeft,
  CaretRight,
  MagnifyingGlass,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { TableSkeleton } from '@/shared/components/TableSkeleton';
import { BUTTON_STYLES, TABLE_STYLES } from '@/shared/constants/theme';
import { alignmentApi } from '../api/syllabusAlignment.api';
import type { AlignmentLevel, AlignmentProcessingStatus } from '../types';

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
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const pageSize = 10;

  const slms = useQuery({
    queryKey: ['syllabus-alignment-slms', page],
    queryFn: () => alignmentApi.listSlms(page, pageSize),
    refetchInterval: (query) =>
      (query.state.data?.items ?? []).some((item) =>
        ['QUEUED', 'RUNNING'].includes(item.current_result?.status ?? ''),
      )
        ? 3000
        : false,
  });

  const total = slms.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const items = slms.data?.items ?? [];
  const filteredItems = items.filter((item) => {
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    return (
      item.title.toLowerCase().includes(query) ||
      (item.course_title && item.course_title.toLowerCase().includes(query)) ||
      (item.lesson_title && item.lesson_title.toLowerCase().includes(query)) ||
      (item.program && item.program.toLowerCase().includes(query))
    );
  });

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-5">
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
          <p className="font-semibold text-text">No SLM documents available</p>
          <p className="text-xs text-text-muted mt-1">Upload course learning modules to begin syllabus alignment checks.</p>
        </div>
      )}

      {/* Unified Table Container */}
      {!slms.isLoading && !slms.isError && items.length > 0 && (
        <div className={TABLE_STYLES.wrapper}>
          {/* Table Search Toolbar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border bg-surface px-4 sm:px-6 py-2.5">
            <div className="relative min-w-[14rem] sm:min-w-[18rem]">
              <MagnifyingGlass
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted"
                aria-hidden="true"
              />
              <input
                type="text"
                placeholder="Search by SLM title, course, or program…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8.5 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
                aria-label="Search syllabus alignments"
              />
            </div>

            <span className="text-xs text-text-muted tabular-nums font-semibold">
              {total} SLM module{total === 1 ? '' : 's'} on record
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[18rem]')}>
                    SLM Document / Module
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Program / Course
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Syllabus Alignment
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
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
                            <span className="text-[11px] text-text-muted truncate max-w-xs">
                              {item.current_result.syllabus_title}
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
