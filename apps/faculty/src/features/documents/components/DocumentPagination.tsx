import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { Dropdown, cn } from "@equiped/ui";

interface DocumentPaginationProps {
  page: number;
  setPage: (page: number | ((prev: number) => number)) => void;
  pageSize: number;
  setPageSize: (size: number) => void;
  totalPages: number;
  total?: number;
  isFetching?: boolean;
  hasFilters?: boolean;
  onResetFilters?: () => void;
}

export function DocumentPagination({
  page,
  setPage,
  pageSize,
  setPageSize,
  totalPages,
  total,
  isFetching = false,
  hasFilters = false,
  onResetFilters,
}: DocumentPaginationProps) {
  return (
    <div className="flex flex-col justify-between gap-3 border-t border-border bg-surface px-4 py-3 text-xs text-text-muted sm:flex-row sm:items-center sm:px-6">
      <div className="flex items-center gap-2">
        <Dropdown
          id="document-page-size"
          label="Rows"
          inlineLabel
          aria-label="Rows per page"
          value={pageSize}
          onChange={(val) => {
            setPageSize(Number(val));
            setPage(1);
          }}
          size="md"
          placement="top"
          options={[
            { value: 10, label: "10 rows" },
            { value: 25, label: "25 rows" },
            { value: 50, label: "50 rows" },
          ]}
        />
      </div>

      <div
        className="text-xs font-medium text-text-muted tabular-nums"
        aria-live="polite"
      >
        {total == null
          ? `Page ${page} of ${totalPages}`
          : total === 0
            ? "0 modules"
            : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total} modules`}
        {hasFilters && (
          <button
            type="button"
            onClick={onResetFilters}
            className="ml-4 min-h-10 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
          >
            Clear filters
          </button>
        )}
      </div>

      {totalPages > 1 && (
        <nav aria-label="Pagination" className="flex items-center gap-1.5">
          <button
            type="button"
            disabled={page === 1 || isFetching}
            aria-label="Previous page"
            onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
            className="inline-flex h-10 items-center justify-center gap-1 rounded-sm border border-border bg-surface px-2.5 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle disabled:opacity-40 disabled:hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <CaretLeft className="size-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">Previous</span>
          </button>

          {Array.from({ length: totalPages }).map((_, idx) => {
            const p = idx + 1;
            const isCurrent = p === page;

            if (
              totalPages > 5 &&
              p !== 1 &&
              p !== totalPages &&
              Math.abs(p - page) > 1
            ) {
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
                aria-current={isCurrent ? "page" : undefined}
                disabled={isFetching}
                onClick={() => setPage(p)}
                className={cn(
                  "inline-flex size-10 items-center justify-center rounded-sm text-xs font-semibold tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isCurrent
                    ? "bg-primary text-primary-foreground font-bold"
                    : "border border-border bg-surface hover:bg-surface-subtle text-text",
                )}
              >
                {p}
              </button>
            );
          })}

          <button
            type="button"
            disabled={page === totalPages || isFetching}
            aria-label="Next page"
            onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
            className="inline-flex h-10 items-center justify-center gap-1 rounded-sm border border-border bg-surface px-2.5 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle disabled:opacity-40 disabled:hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="hidden sm:inline">Next</span>
            <CaretRight className="size-3.5" aria-hidden="true" />
          </button>
        </nav>
      )}
    </div>
  );
}
