// Self-contained table -- deliberately NOT importing
// history/components/EvaluationHistoryTable.tsx, since features must stay
// self-contained (CLAUDE.md module boundaries). Visually mirrors it
// (meta bar + status-badge table) so the two history views feel
// consistent, but this is its own implementation.
import { useEffect, useState } from 'react';
import { AlertTriangle, ExternalLink, Loader2, Trash2 } from 'lucide-react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES } from '@/shared/constants/theme';
import { getErrorMessage } from '@/shared/api/http';
import { useDeleteAlignmentCheck } from '../hooks/useDeleteAlignmentCheck';
import { useAlignmentCheckHistory } from '../hooks/useAlignmentCheckHistory';
import { ConfirmDeleteModal } from './ConfirmDeleteModal';
import type { AlignmentCheckListItem } from '../types';

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

type AlignmentHistoryListProps = {
  onSelect: (item: AlignmentCheckListItem) => void;
};

export function AlignmentHistoryList({ onSelect }: AlignmentHistoryListProps) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [pendingDelete, setPendingDelete] = useState<AlignmentCheckListItem | null>(null);
  const { data, isLoading, isError, error } = useAlignmentCheckHistory(page, pageSize);
  const deleteCheck = useDeleteAlignmentCheck();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);

  // Auto-clamp to valid page when empty pagination occurs (stale page after delete)
  useEffect(() => {
    if (!isLoading && items.length === 0 && page > 1) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPage(Math.max(page - 1, 1));
    }
  }, [isLoading, items.length, page]);

  const handleConfirmDelete = () => {
    if (!pendingDelete) return;
    deleteCheck.mutate(pendingDelete.check_id, {
      onSuccess: () => setPendingDelete(null),
    });
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-md border border-border bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-subtle px-6 py-4">
        <p className="text-sm font-medium text-text-muted">
          {isLoading
            ? 'Loading records…'
            : `${total} check${total === 1 ? '' : 's'} found`}
        </p>
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          Advisory only.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {isError ? (
          <div className="flex items-center gap-2 rounded-sm border border-destructive/20 bg-destructive-soft px-4 py-3 text-sm font-semibold text-destructive">
            <AlertTriangle className="size-4 shrink-0" />
            {getErrorMessage(error, 'Could not load check history.')}
          </div>
        ) : null}

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm font-semibold text-text-muted">
            <Loader2 className="size-5 animate-spin text-primary" />
            <span>Loading check history…</span>
          </div>
        ) : null}

        {!isError && !isLoading && items.length === 0 ? (
          <div className="grid gap-2 rounded-sm border border-dashed border-border px-6 py-12 text-center bg-surface">
            <h3 className="text-lg font-semibold text-text">No checks yet</h3>
            <p className="text-sm text-text-muted">
              Pick a document and course above, then run a check to see it here.
            </p>
          </div>
        ) : null}

        {!isError && !isLoading && items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th className={cn(TABLE_STYLES.th, 'min-w-[20rem]')}>
                    Document / Course
                  </th>
                  <th className={TABLE_STYLES.th}>Status</th>
                  <th className={TABLE_STYLES.th}>Run at</th>
                  <th className={cn(TABLE_STYLES.th, 'text-right')}>Action</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {items.map((item: AlignmentCheckListItem) => (
                  <tr key={item.check_id} className={TABLE_STYLES.tr}>
                    <td className={cn(TABLE_STYLES.td, 'font-semibold text-text')}>
                      <div className="flex flex-col gap-0.5">
                        <span className="max-w-[22rem] truncate">{item.document_title}</span>
                        <span className="text-xs font-medium text-text-muted">
                          {item.course_title}
                        </span>
                      </div>
                    </td>
                    <td className={TABLE_STYLES.td}>
                      <Badge variant={item.success ? 'success' : 'destructive'} withDot>
                        {item.success ? 'Completed' : 'Failed'}
                      </Badge>
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-text-muted')}>
                      {formatDate(item.run_at)}
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-right')}>
                      <div className="inline-flex items-center gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => onSelect(item)}
                        >
                          <span>View</span>
                          <ExternalLink className="ml-1.5 size-3" aria-hidden="true" />
                        </Button>
                        <button
                          type="button"
                          onClick={() => setPendingDelete(item)}
                          disabled={deleteCheck.isPending}
                          aria-label="Delete check"
                          className="inline-flex size-8 items-center justify-center rounded-sm text-text-muted transition-colors hover:bg-destructive-soft hover:text-destructive focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      {pendingDelete ? (
        <ConfirmDeleteModal
          title="Delete this check?"
          message={`This will permanently delete the check for "${pendingDelete.document_title}" / "${pendingDelete.course_title}". This cannot be undone.`}
          isPending={deleteCheck.isPending}
          errorMessage={
            deleteCheck.isError
              ? getErrorMessage(deleteCheck.error, 'Could not delete this check.')
              : null
          }
          onConfirm={handleConfirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      ) : null}

      {items.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border bg-surface-subtle px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">Show</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="h-8 cursor-pointer rounded-sm border border-input bg-surface px-2 text-xs font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value={10}>10 rows</option>
              <option value={25}>25 rows</option>
              <option value={50}>50 rows</option>
            </select>
          </div>

          <div className="text-xs font-semibold uppercase tracking-wider tabular-nums text-text-muted">
            Page {page} of {totalPages}
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
            >
              Previous
            </Button>

            {Array.from({ length: totalPages }).map((_, idx) => {
              const p = idx + 1;
              const isCurrent = p === page;

              if (totalPages > 5 && p !== 1 && p !== totalPages && Math.abs(p - page) > 1) {
                if (p === 2 && page > 3) {
                  return (
                    <span
                      key="dots-start"
                      className="select-none px-1 text-xs font-semibold text-text-muted"
                    >
                      ...
                    </span>
                  );
                }
                if (p === totalPages - 1 && page < totalPages - 2) {
                  return (
                    <span
                      key="dots-end"
                      className="select-none px-1 text-xs font-semibold text-text-muted"
                    >
                      ...
                    </span>
                  );
                }
                return null;
              }

              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPage(p)}
                  className={cn(
                    'inline-flex size-8 items-center justify-center rounded-sm text-xs font-semibold tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isCurrent
                      ? 'bg-primary text-primary-foreground'
                      : 'border border-border bg-surface text-text hover:bg-surface-subtle',
                  )}
                >
                  {p}
                </button>
              );
            })}

            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={page === totalPages}
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
