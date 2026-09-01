interface MatrixFiltersProps {
  program: string;
  status: string;
  onProgramChange: (val: string) => void;
  onStatusChange: (val: string) => void;
}

const SELECT_ARROW_BG =
  "bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20256%20256%22%20fill%3D%22%23596579%22%3E%3Cpath%20d%3D%22M213.66%2C101.66l-80%2C80a8%2C8%2C0%2C0%2C1-11.32%2C0l-80-80A8%2C8%2C0%2C0%2C1%2C53.66%2C90.34L128%2C164.69l74.34-74.35a8%2C8%2C0%2C0%2C1%2C11.32%2C11.32Z%22%2F%3E%3C%2Fsvg%3E')] bg-[position:right_14px_center] bg-[size:14px] bg-no-repeat";

export function MatrixFilters({
  program,
  status,
  onProgramChange,
  onStatusChange,
}: MatrixFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-border bg-surface px-5 py-4">
      <div className="flex-1 min-w-[200px] max-w-xs">
        <select
          value={program}
          onChange={(e) => onProgramChange(e.target.value)}
          aria-label="Filter by program"
          className={`w-full h-10 appearance-none border border-input bg-surface pl-3.5 pr-10 rounded-sm text-xs sm:text-sm font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer transition-colors ${SELECT_ARROW_BG}`}
        >
          <option value="all">All Programs</option>
          <option value="BSCS">Computer Science</option>
          <option value="BSInfoTech">Information Technology</option>
        </select>
      </div>

      <div className="flex-1 min-w-[200px] max-w-xs">
        <select
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
          aria-label="Filter by status"
          className={`w-full h-10 appearance-none border border-input bg-surface pl-3.5 pr-10 rounded-sm text-xs sm:text-sm font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer transition-colors ${SELECT_ARROW_BG}`}
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
