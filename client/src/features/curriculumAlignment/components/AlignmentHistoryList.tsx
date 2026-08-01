// Self-contained pagination -- deliberately NOT importing
// dashboard/components/DocumentPagination.tsx, since features must stay
// self-contained (CLAUDE.md module boundaries). Same reasoning
// SlmReadingPane.tsx already documents for its own click-to-scroll reimpl.
import { useState } from 'react';
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { useAlignmentCheckHistory } from '../hooks/useAlignmentCheckHistory';
import { useDeleteAlignmentCheck } from '../hooks/useDeleteAlignmentCheck';
import { formatSummaryChips } from '../utils/historyHelpers';
import type { AlignmentCheckListItem } from '../types';

const PAGE_SIZE = 20;

type AlignmentHistoryListProps = {
  onSelect: (item: AlignmentCheckListItem) => void;
};

export function AlignmentHistoryList({ onSelect }: AlignmentHistoryListProps) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error } = useAlignmentCheckHistory(page, PAGE_SIZE);
  const deleteCheck = useDeleteAlignmentCheck();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);

  const handleDelete = (item: AlignmentCheckListItem, event: React.MouseEvent) => {
    event.stopPropagation();
    const confirmed = window.confirm(
      `Delete this check (${item.document_title} / ${item.course_title})?`,
    );
    if (!confirmed) return;
    deleteCheck.mutate(item.check_id);
  };

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-8 animate-spin text-[#1b3b87]" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-sm font-semibold text-[#b91c1c]">
        <AlertTriangle className="size-4 shrink-0" />
        {getErrorMessage(error, 'Could not load check history.')}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-sm border border-dashed border-slate-200 bg-slate-50/30 p-8 text-center text-sm font-semibold text-slate-500">
        No checks yet. Pick a document and course above, then run a check to see it here.
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-sm border border-slate-200 bg-white">
      <div className="flex-1 divide-y divide-slate-100 overflow-y-auto">
        {items.map((item) => (
          <div
            key={item.check_id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(item)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect(item);
              }
            }}
            className="flex cursor-pointer items-start justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#1b3b87]"
          >
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-slate-800">
                {item.document_title}
                <span className="mx-1.5 text-slate-300">/</span>
                <span className="text-slate-600">{item.course_title}</span>
              </div>
              <div className="mt-1 text-xs text-slate-500">
                {new Date(item.run_at).toLocaleString()}
              </div>
              <div className="mt-1 text-xs font-medium text-slate-600">
                {item.success
                  ? formatSummaryChips(item.summary)
                  : `Failed: ${item.error_message ?? 'unknown error'}`}
              </div>
            </div>
            <button
              type="button"
              onClick={(e) => handleDelete(item, e)}
              aria-label="Delete check"
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-sm text-slate-400 transition-colors hover:bg-[#b91c1c]/10 hover:text-[#b91c1c] focus:outline-none focus:ring-2 focus:ring-[#b91c1c]"
            >
              <Trash2 className="size-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/30 px-4 py-3">
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
    </div>
  );
}
