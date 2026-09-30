import { Button, Dropdown } from '@equiped/ui';

const PAGE_SIZE_OPTIONS = [10, 20, 50].map((value) => ({
  value,
  label: String(value),
}));

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
    <nav
      aria-label="Preference log pagination"
      className="flex flex-wrap items-center justify-between gap-4 text-sm text-text-muted"
    >
      <div className="flex flex-wrap items-center gap-4">
        <span>
          Showing{' '}
          <strong className="font-semibold text-text tabular-nums">
            {startRecord}–{endRecord}
          </strong>{' '}
          of{' '}
          <strong className="font-semibold text-text tabular-nums">
            {totalRecords}
          </strong>{' '}
          records
        </span>

        <Dropdown
          value={pageSize}
          onChange={onPageSizeChange}
          options={PAGE_SIZE_OPTIONS}
          label="Rows per page"
          inlineLabel
          size="md"
          aria-label="Records per page"
          menuClassName="top-auto bottom-full mt-0 mb-1"
        />
      </div>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
        >
          Previous
        </Button>
        <span className="px-2 tabular-nums">
          Page <strong className="font-medium text-text">{page}</strong> of{' '}
          {totalPages}
        </span>
        <Button
          type="button"
          variant="secondary"
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
