import { Dropdown } from '@equiped/ui';

interface MatrixFiltersProps {
  program: string;
  status: string;
  onProgramChange: (val: string) => void;
  onStatusChange: (val: string) => void;
}

export function MatrixFilters({
  program,
  status,
  onProgramChange,
  onStatusChange,
}: MatrixFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-border bg-surface px-5 py-4">
      <div className="flex-1 min-w-[200px] max-w-xs">
        <Dropdown
          value={program}
          onChange={onProgramChange}
          aria-label="Filter by program"
          size="md"
          className="w-full"
          options={[
            { value: 'all', label: 'All Programs' },
            { value: 'BSCS', label: 'Computer Science' },
            { value: 'BSInfoTech', label: 'Information Technology' },
          ]}
        />
      </div>

      <div className="flex-1 min-w-[200px] max-w-xs">
        <Dropdown
          value={status}
          onChange={onStatusChange}
          aria-label="Filter by status"
          size="md"
          className="w-full"
          options={[
            { value: 'all', label: 'All Statuses' },
            { value: 'COMPLETED', label: 'Completed' },
            { value: 'FAILED', label: 'Failed' },
            { value: 'EVALUATING', label: 'Evaluating' },
          ]}
        />
      </div>
    </div>
  );
}
