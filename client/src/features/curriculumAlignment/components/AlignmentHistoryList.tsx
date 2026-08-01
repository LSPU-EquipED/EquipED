// Self-contained table -- deliberately NOT importing
// history/components/EvaluationHistoryTable.tsx, since features must stay
// self-contained (CLAUDE.md module boundaries). Visually mirrors it
// (meta bar + status-badge table) so the two history views feel
// consistent, but this is its own implementation.
import { useEffect, useState } from 'react';
import { AlertTriangle, ExternalLink, Loader2, Trash2 } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { useAlignmentCheckHistory } from '../hooks/useAlignmentCheckHistory';
import { useDeleteAlignmentCheck } from '../hooks/useDeleteAlignmentCheck';
import { ConfirmDeleteModal } from './ConfirmDeleteModal';
import type { AlignmentCheckListItem } from '../types';

const PAGE_SIZE = 20;

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
  const [pendingDelete, setPendingDelete] = useState<AlignmentCheckListItem | null>(null);
  const { data, isLoading, isError, error } = useAlignmentCheckHistory(page, PAGE_SIZE);
  const deleteCheck = useDeleteAlignmentCheck();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);

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
    <div className="flex flex-1 flex-col overflow-hidden rounded-sm border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/50 px-6 py-4">
        <p className="text-sm font-medium text-slate-600">
          {isLoading
            ? 'Loading records…'
            : `${total} check${total === 1 ? '' : 's'} found`}
        </p>
        <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
          Advisory only.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {isError ? (
          <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]">
            <AlertTriangle className="size-4 shrink-0" />
            {getErrorMessage(error, 'Could not load check history.')}
          </div>
        ) : null}

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm font-semibold text-slate-500">
            <Loader2 className="size-5 animate-spin text-[#1b3b87]" />
            <span>Loading check history…</span>
          </div>
        ) : null}

        {!isError && !isLoading && items.length === 0 ? (
          <div className="grid gap-2 rounded-sm border border-dashed border-slate-200 px-6 py-12 text-center">
            <h3 className="text-lg font-semibold text-slate-800">No checks yet</h3>
            <p className="text-sm text-slate-500">
              Pick a document and course above, then run a check to see it here.
            </p>
          </div>
        ) : null}

        {!isError && !isLoading && items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse border-spacing-0 text-left">
              <thead className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-600">
                <tr>
                  <th className="min-w-[20rem] px-4 py-3 font-semibold text-slate-500">
                    Document / Course
                  </th>
                  <th className="px-4 py-3 font-semibold text-slate-500">Status</th>
                  <th className="px-4 py-3 font-semibold text-slate-500">Run at</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {items.map((item) => (
                  <tr key={item.check_id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                      <div className="flex flex-col gap-0.5">
                        <span className="max-w-[22rem] truncate">{item.document_title}</span>
                        <span className="text-xs font-medium text-slate-400">
                          {item.course_title}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span
                        className={`inline-flex items-center rounded-sm px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                          item.success ? 'bg-[#3b963e] text-white' : 'bg-[#b91c1c] text-white'
                        }`}
                      >
                        {item.success ? 'Completed' : 'Failed'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-slate-600">
                      {formatDate(item.run_at)}
                    </td>
                    <td className="px-4 py-3 text-right text-sm">
                      <div className="inline-flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => onSelect(item)}
                          className="inline-flex h-8 items-center justify-center rounded-sm border border-slate-200 px-3 text-xs font-bold uppercase tracking-wider text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                        >
                          <span>View</span>
                          <ExternalLink className="ml-1.5 size-3" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setPendingDelete(item)}
                          disabled={deleteCheck.isPending}
                          aria-label="Delete check"
                          className="inline-flex size-8 items-center justify-center rounded-sm text-slate-400 transition-colors hover:bg-[#b91c1c]/10 hover:text-[#b91c1c] focus:outline-none focus:ring-2 focus:ring-[#b91c1c] disabled:cursor-not-allowed disabled:opacity-50"
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
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/30 px-6 py-3">
          <button
            type="button"
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(p - 1, 1))}
            className="inline-flex h-8 items-center justify-center rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
            className="inline-flex h-8 items-center justify-center rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}
