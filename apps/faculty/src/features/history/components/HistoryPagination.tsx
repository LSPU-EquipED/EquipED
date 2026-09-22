import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import { Button, Dropdown } from '@equiped/ui';

interface HistoryPaginationProps {
  page: number;
  pageSize: number;
  totalPages: number;
  total: number;
  onPageChange: (page: number | ((previousPage: number) => number)) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function HistoryPagination({
  page,
  pageSize,
  totalPages,
  total,
  onPageChange,
  onPageSizeChange,
}: HistoryPaginationProps) {
  return (
    <div className="flex flex-col gap-3 border-t border-border bg-surface-subtle/65 px-4 py-3 text-xs text-text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-medium tabular-nums">
          Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total} evaluations
        </span>
        <span className="hidden text-border sm:inline" aria-hidden="true">|</span>
        <Dropdown
          id="history-page-size"
          aria-label="Rows per page"
          label="Show"
          inlineLabel
          size="sm"
          value={pageSize}
          onChange={(value) => onPageSizeChange(Number(value))}
          options={[
            { value: 10, label: '10 rows' },
            { value: 25, label: '25 rows' },
            { value: 50, label: '50 rows' },
          ]}
        />
      </div>

      <nav aria-label="Pagination" className="flex items-center gap-1">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange((currentPage) => Math.max(1, currentPage - 1))}
          className="h-7 px-2 text-xs"
          aria-label="Previous page"
        >
          <CaretLeft className="size-3" aria-hidden="true" />
          <span className="hidden sm:inline">Previous</span>
        </Button>
        <span className="px-2 font-medium tabular-nums text-text" aria-live="polite">
          {page} / {totalPages}
        </span>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange((currentPage) => Math.min(totalPages, currentPage + 1))}
          className="h-7 px-2 text-xs"
          aria-label="Next page"
        >
          <span className="hidden sm:inline">Next</span>
          <CaretRight className="size-3" aria-hidden="true" />
        </Button>
      </nav>
    </div>
  );
}
