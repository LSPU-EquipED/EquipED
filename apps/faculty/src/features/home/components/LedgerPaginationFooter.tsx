import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { Link } from "@tanstack/react-router";
import { Button, Dropdown } from "@equiped/ui";

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
    <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-3 rounded-b-md border-t border-border bg-surface px-4 py-3 text-sm text-text-muted sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className="tabular-nums font-medium">
          Showing {(safePage - 1) * pageSize + 1}–
          {Math.min(safePage * pageSize, totalItems)} of {totalItems} items
        </span>
        <Dropdown
          aria-label="Rows per page"
          size="md"
          value={pageSize}
          onChange={onPageSizeChange}
          options={[
            { value: 5, label: "5 rows" },
            { value: 10, label: "10 rows" },
            { value: 20, label: "20 rows" },
          ]}
          menuClassName="top-auto bottom-full mb-1 mt-0"
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <nav
          aria-label="Evaluation activity pagination"
          className="flex items-center gap-1"
        >
          <Button
            type="button"
            variant="secondary"
            size="md"
            disabled={safePage <= 1}
            onClick={() => onPageChange((p) => Math.max(1, p - 1))}
            className="w-10 px-0"
            aria-label="Previous page"
            title="Previous page"
          >
            <CaretLeft className="size-4" aria-hidden="true" />
          </Button>
          <span
            className="px-2 text-xs font-medium tabular-nums text-text"
            aria-live="polite"
            aria-atomic="true"
          >
            {safePage} / {totalPages}
          </span>
          <Button
            type="button"
            variant="secondary"
            size="md"
            disabled={safePage >= totalPages}
            onClick={() => onPageChange((p) => Math.min(totalPages, p + 1))}
            className="w-10 px-0"
            aria-label="Next page"
            title="Next page"
          >
            <CaretRight className="size-4" aria-hidden="true" />
          </Button>
        </nav>

        <Link
          to="/evaluations"
          className="inline-flex min-h-10 items-center gap-1 rounded-sm font-medium text-primary transition-colors hover:text-primary-strong hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <span>Evaluation history</span>
          <CaretRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
