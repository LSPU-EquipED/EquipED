import { CaretLeft, CaretRight } from "@phosphor-icons/react";
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
          placement="top"
        />
      </div>

      <nav
        aria-label="Evaluation activity pagination"
        className="flex items-center gap-1"
      >
        <Button
          type="button"
          variant="secondary"
          size="icon"
          disabled={safePage <= 1}
          onClick={() => onPageChange((p) => Math.max(1, p - 1))}
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
          size="icon"
          disabled={safePage >= totalPages}
          onClick={() => onPageChange((p) => Math.min(totalPages, p + 1))}
          aria-label="Next page"
          title="Next page"
        >
          <CaretRight className="size-4" aria-hidden="true" />
        </Button>
      </nav>
    </div>
  );
}
