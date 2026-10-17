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
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 rounded-b-md border-t border-border bg-surface px-4 py-3 text-xs text-text-muted sm:px-6">
      <Dropdown
        id="history-page-size"
        aria-label="Rows per page"
        label="Rows"
        inlineLabel
        size="md"
        placement="top"
        value={pageSize}
        onChange={(value) => onPageSizeChange(Number(value))}
        options={[
          { value: 10, label: '10 rows' },
          { value: 25, label: '25 rows' },
          { value: 50, label: '50 rows' },
        ]}
      />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <span className="tabular-nums">
          {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of{' '}
          {total} evaluations
        </span>
        {totalPages > 1 && (
          <nav
            aria-label="Pagination"
            className="flex shrink-0 items-center gap-1"
          >
            <Button
              type="button"
              variant="secondary"
              size="md"
              disabled={page <= 1}
              onClick={() =>
                onPageChange((currentPage) => Math.max(1, currentPage - 1))
              }
              className="px-3 text-xs"
              aria-label="Previous page"
            >
              <CaretLeft className="size-3" aria-hidden="true" />
              <span className="hidden sm:inline">Previous</span>
            </Button>
            <span
              className="whitespace-nowrap px-2 font-medium tabular-nums text-text"
              aria-live="polite"
            >
              {page} / {totalPages}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="md"
              disabled={page >= totalPages}
              onClick={() =>
                onPageChange((currentPage) =>
                  Math.min(totalPages, currentPage + 1),
                )
              }
              className="px-3 text-xs"
              aria-label="Next page"
            >
              <span className="hidden sm:inline">Next</span>
              <CaretRight className="size-3" aria-hidden="true" />
            </Button>
          </nav>
        )}
      </div>
    </div>
  );
}
