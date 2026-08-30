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
    <div className="mb-6 flex flex-wrap items-center gap-4">
      <div className="flex-1 min-w-[200px] max-w-sm">
        <select
          value={program}
          onChange={(e) => onProgramChange(e.target.value)}
          aria-label="Filter by program"
          className="w-full h-10 border border-input bg-surface px-3 focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent rounded-sm text-sm font-semibold text-text cursor-pointer transition-colors"
        >
          <option value="all">All Programs</option>
          <option value="BSCS">Computer Science</option>
          <option value="BSInfoTech">Information Technology</option>
        </select>
      </div>

      <div className="flex-1 min-w-[200px] max-w-sm">
        <select
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
          aria-label="Filter by status"
          className="w-full h-10 border border-input bg-surface px-3 focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent rounded-sm text-sm font-semibold text-text cursor-pointer transition-colors"
        >
          <option value="all">All Statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="FAILED">Failed</option>
          <option value="EVALUATING">Evaluating</option>
        </select>
      </div>
    </div>
  );
}
