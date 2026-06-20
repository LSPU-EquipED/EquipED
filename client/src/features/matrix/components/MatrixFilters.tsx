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
          className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-850 cursor-pointer"
        >
          <option value="all">All Programs</option>
          <option value="BSCS">Computer Science</option>
          <option value="BSIT">Information Technology</option>
          <option value="BSEd">Education</option>
        </select>
      </div>

      <div className="flex-1 min-w-[200px] max-w-sm">
        <select
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
          className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-850 cursor-pointer"
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
