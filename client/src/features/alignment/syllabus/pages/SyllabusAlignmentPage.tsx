import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { AlertTriangle, BookOpenCheck, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
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
  const pageSize = 20;
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
  const totalPages = Math.max(1, Math.ceil((slms.data?.total ?? 0) / pageSize));

  return (
    <section className="px-6 py-7">
      <header className="border-b border-border pb-5">
        <div className="flex items-center gap-3">
          <BookOpenCheck className="size-6 text-primary" aria-hidden="true" />
          <div>
            <h1 className="text-2xl font-bold text-text">Syllabus Alignment</h1>
            <p className="mt-1 text-sm text-text-muted">
              Check whether substantial SLM topics are included in an approved syllabus.
            </p>
          </div>
        </div>
      </header>

      {slms.isLoading && (
        <div className="flex items-center gap-2 border-b border-border py-6 text-sm font-semibold text-text-muted">
          <Loader2 className="size-4 animate-spin text-primary" aria-hidden="true" /> Loading SLM documents…
        </div>
      )}
      {slms.isError && (
        <div className="mt-5 flex items-center gap-2 rounded-sm border border-destructive/20 bg-destructive-soft p-4 text-sm font-semibold text-destructive">
          <AlertTriangle className="size-4" aria-hidden="true" />
          {getErrorMessage(slms.error, 'Unable to load SLM documents.')}
        </div>
      )}
      {!slms.isLoading && !slms.isError && slms.data?.items.length === 0 && (
        <p className="mt-5 rounded-sm border border-dashed border-border bg-surface p-6 text-center text-sm text-text-muted">
          No SLM documents are available. Upload an SLM before starting syllabus alignment.
        </p>
      )}
      {!!slms.data?.items.length && (
        <div className={cn('mt-5', TABLE_STYLES.wrapper)}>
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th className={TABLE_STYLES.th}>SLM document</th>
                  <th className={TABLE_STYLES.th}>Program / course</th>
                  <th className={TABLE_STYLES.th}>Current alignment</th>
                  <th className={cn(TABLE_STYLES.th, 'text-right')}>Action</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {slms.data.items.map((item) => (
                  <tr key={item.document_id} className={TABLE_STYLES.tr}>
                    <td className={TABLE_STYLES.td}>
                      <p className="font-bold text-text">{item.title}</p>
                      <p className="mt-0.5 text-xs text-text-muted">
                        {item.lesson_title || item.course_title || 'No lesson title'}
                      </p>
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-text-muted')}>
                      {[item.program, item.course_code].filter(Boolean).join(' · ') ||
                        'Not specified'}
                    </td>
                    <td className={TABLE_STYLES.td}>
                      {item.current_result ? (
                        <div>
                          <Badge variant={getLevelBadgeVariant(item.current_result.status, item.current_result.alignment_level)} withDot>
                            {statusLabel(item.current_result.status, item.current_result.alignment_level)}
                          </Badge>
                          <p className="mt-1 text-xs text-text-muted">
                            {item.current_result.syllabus_title}
                          </p>
                        </div>
                      ) : (
                        <span className="text-xs font-semibold text-text-muted">
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
                              className={cn(BUTTON_STYLES.base, BUTTON_STYLES.variants.secondary, BUTTON_STYLES.sizes.sm)}
                            >
                              View Result
                            </Link>
                          ) : ['QUEUED', 'RUNNING'].includes(item.current_result?.status ?? '') ? (
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              disabled
                              isLoading
                            >
                              Running
                            </Button>
                          ) : (
                            <Link
                              to="/syllabus-alignment/$documentId"
                              params={{ documentId: item.document_id }}
                              className={cn(BUTTON_STYLES.base, BUTTON_STYLES.variants.primary, BUTTON_STYLES.sizes.sm)}
                            >
                              {item.current_result?.status === 'FAILED'
                                  ? 'Retry'
                                  : 'Evaluate'}
                              <ChevronRight className="size-3.5" aria-hidden="true" />
                            </Link>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs font-semibold text-text-muted">
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
            <footer className="flex items-center justify-between border-t border-border bg-surface-subtle px-4 py-3">
              <p className="text-xs font-semibold text-text-muted tabular-nums">
                Page {page} of {totalPages} · {slms.data.total} SLM documents
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  disabled={page === 1 || slms.isFetching}
                >
                  <ChevronLeft className="size-3.5" aria-hidden="true" /> Previous
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  disabled={page === totalPages || slms.isFetching}
                >
                  Next <ChevronRight className="size-3.5" aria-hidden="true" />
                </Button>
              </div>
            </footer>
          )}
        </div>
      )}
    </section>
  );
}
