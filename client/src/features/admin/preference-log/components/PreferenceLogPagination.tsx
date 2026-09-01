import { Button } from '@/shared/components/Button';

interface PreferenceLogPaginationProps {
  page: number;
  pageSize: number;
  totalRecords: number;
  onPageChange: (newPage: number) => void;
  onPageSizeChange: (newPageSize: number) => void;
}

export function PreferenceLogPagination({
  page,
  pageSize,
  totalRecords,
  onPageChange,
  onPageSizeChange,
}: PreferenceLogPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const startRecord = totalRecords > 0 ? (page - 1) * pageSize + 1 : 0;
  const endRecord = Math.min(page * pageSize, totalRecords);

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-border bg-surface px-5 py-3 text-xs text-text-muted">
      <div className="flex flex-wrap items-center gap-4">
        <span>
          Showing{' '}
          <strong className="font-semibold text-text tabular-nums">
            {startRecord}–{endRecord}
          </strong>{' '}
          of <strong className="font-semibold text-text tabular-nums">{totalRecords}</strong> records
        </span>

        <div className="flex items-center gap-1.5 pl-3 border-l border-border">
          <span className="text-[11px] text-text-muted font-medium">Per page:</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            aria-label="Records per page"
            className="h-7 border border-input bg-surface px-2 rounded-xs text-xs font-semibold text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
          >
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="h-7 px-2.5 text-xs font-semibold"
        >
          Previous
        </Button>
        <span className="px-2 text-xs font-medium text-text">
          Page <strong className="font-bold tabular-nums">{page}</strong> of{' '}
          <strong className="font-bold tabular-nums">{totalPages}</strong>
        </span>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="h-7 px-2.5 text-xs font-semibold"
        >
          Next
        </Button>
      </div>
    </div>
  );
}
