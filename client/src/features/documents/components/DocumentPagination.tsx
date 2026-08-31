import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';

interface DocumentPaginationProps {
  page: number;
  setPage: (page: number | ((prev: number) => number)) => void;
  pageSize: number;
  setPageSize: (size: number) => void;
  totalPages: number;
}

export function DocumentPagination({
  page,
  setPage,
  pageSize,
  setPageSize,
  totalPages,
}: DocumentPaginationProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-border bg-surface-subtle px-4 sm:px-6 py-3">
      <div className="flex items-center gap-2">
        <label
          htmlFor="document-page-size"
          className="text-xs text-text-muted font-semibold uppercase tracking-wider"
        >
          Show
        </label>
        <select
          id="document-page-size"
          aria-label="Rows per page"
          value={pageSize}
          onChange={(e) => {
            setPageSize(Number(e.target.value));
            setPage(1);
          }}
          className="h-8 rounded-sm border border-input bg-surface px-2 text-xs font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
        >
          <option value={10}>10 rows</option>
          <option value={25}>25 rows</option>
          <option value={50}>50 rows</option>
        </select>
      </div>

      <div
        className="text-xs font-semibold text-text-muted uppercase tracking-wider tabular-nums"
        aria-live="polite"
      >
        Page {page} of {totalPages}
      </div>

      <nav aria-label="Pagination" className="flex items-center gap-1.5">
        <button
          type="button"
          disabled={page === 1}
          aria-label="Previous page"
          onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
          className="inline-flex h-8 items-center justify-center gap-1 rounded-sm border border-border bg-surface px-2.5 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle disabled:opacity-40 disabled:hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <CaretLeft className="size-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Previous</span>
        </button>

        {Array.from({ length: totalPages }).map((_, idx) => {
          const p = idx + 1;
          const isCurrent = p === page;

          if (totalPages > 5 && p !== 1 && p !== totalPages && Math.abs(p - page) > 1) {
            if (p === 2 && page > 3) {
              return (
                <span
                  key="dots-start"
                  aria-hidden="true"
                  className="px-1 text-xs font-bold text-text-muted select-none"
                >
                  ...
                </span>
              );
            }
            if (p === totalPages - 1 && page < totalPages - 2) {
              return (
                <span
                  key="dots-end"
                  aria-hidden="true"
                  className="px-1 text-xs font-bold text-text-muted select-none"
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
              aria-label={`Page ${p}`}
              aria-current={isCurrent ? 'page' : undefined}
              onClick={() => setPage(p)}
              className={cn(
                'inline-flex size-8 items-center justify-center rounded-sm text-xs font-semibold tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isCurrent
                  ? 'bg-primary text-primary-foreground font-bold'
                  : 'border border-border bg-surface hover:bg-surface-subtle text-text',
              )}
            >
              {p}
            </button>
          );
        })}

        <button
          type="button"
          disabled={page === totalPages}
          aria-label="Next page"
          onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
          className="inline-flex h-8 items-center justify-center gap-1 rounded-sm border border-border bg-surface px-2.5 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle disabled:opacity-40 disabled:hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="hidden sm:inline">Next</span>
          <CaretRight className="size-3.5" aria-hidden="true" />
        </button>
      </nav>
    </div>
  );
}
