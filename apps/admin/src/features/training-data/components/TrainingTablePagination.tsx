import { Button, Dropdown } from '@equiped/ui';
import type { TrainingTablePaginationControls } from '../types';

const PAGE_SIZE_OPTIONS = [5, 10, 20].map((value) => ({ value, label: String(value) }));

interface TrainingTablePaginationProps {
  label: string;
  pagination: TrainingTablePaginationControls;
}

export function TrainingTablePagination({ label, pagination }: TrainingTablePaginationProps) {
  const { page, pageSize, totalPages, totalRecords, onPageChange, onPageSizeChange } = pagination;
  if (!pagination.showPagination) return null;

  return (
    <nav
      aria-label={`${label} pagination`}
      className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 border-t border-border pt-3 text-xs leading-5 text-text-muted"
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span aria-live="polite" aria-atomic="true" className="tabular-nums">
          {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, totalRecords)} of {totalRecords}
        </span>
        <Dropdown
          value={pageSize}
          onChange={onPageSizeChange}
          options={PAGE_SIZE_OPTIONS}
          label="Rows per page"
          inlineLabel
          size="sm"
          aria-label={`${label} rows per page`}
          menuClassName="top-auto bottom-full mt-0 mb-1"
        />
      </div>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          Previous
        </Button>
        <span className="px-1 tabular-nums">
          Page {page} / {totalPages}
        </span>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
