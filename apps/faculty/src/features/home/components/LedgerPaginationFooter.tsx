import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { Link } from "@tanstack/react-router";
import { Button } from "@equiped/ui";

export interface LedgerPaginationFooterProps {
  safePage: number;
  pageSize: number;
  totalPages: number;
  totalItems: number;
  onPageChange: (page: number | ((prev: number) => number)) => void;
  onPageSizeChange: (size: number) => void;
}

export function LedgerPaginationFooter({
  safePage,
  pageSize,
  totalPages,
  totalItems,
  onPageChange,
  onPageSizeChange,
}: LedgerPaginationFooterProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-t border-border bg-surface-subtle px-4 sm:px-6 py-2.5 text-xs text-text-muted">
      <div className="flex flex-wrap items-center gap-3">
        <span className="tabular-nums font-medium">
          Showing {(safePage - 1) * pageSize + 1}–
          {Math.min(safePage * pageSize, totalItems)} of {totalItems} items
        </span>
        <span className="text-border">|</span>
        <div className="flex items-center gap-1.5">
          <span>Show</span>
          <select
            aria-label="Rows per page"
            value={pageSize}
            onChange={(e) => {
              onPageSizeChange(Number(e.target.value));
              onPageChange(1);
            }}
            className="h-7 rounded-sm border border-input bg-surface px-1.5 text-xs font-semibold text-text focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
          </select>
          <span>per page</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={safePage <= 1}
            onClick={() => onPageChange((p) => Math.max(1, p - 1))}
            className="h-7 px-2 text-xs"
            aria-label="Previous page"
          >
            <CaretLeft className="size-3" aria-hidden="true" />
            <span className="hidden sm:inline">Previous</span>
          </Button>
          <span className="px-2 font-medium tabular-nums text-text">
            {safePage} / {totalPages}
          </span>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={safePage >= totalPages}
            onClick={() => onPageChange((p) => Math.min(totalPages, p + 1))}
            className="h-7 px-2 text-xs"
            aria-label="Next page"
          >
            <span className="hidden sm:inline">Next</span>
            <CaretRight className="size-3" aria-hidden="true" />
          </Button>
        </div>

        <span className="text-border">|</span>

        <Link
          to="/evaluations"
          className="font-semibold text-primary hover:text-primary-strong flex items-center gap-1 transition-colors"
        >
          <span>Evaluation history</span>
          <CaretRight className="size-3" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
