interface HistoryFiltersProps {
  status: string;
  onStatusChange: (val: string) => void;
}

export function HistoryFilters({ status, onStatusChange }: HistoryFiltersProps) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-4">
      <div className="w-full sm:w-[200px]">
        <select
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
          className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-850 cursor-pointer"
        >
          <option value="all">All Statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="FAILED">Failed</option>
          <option value="EVALUATING">Evaluating</option>
          <option value="SUBMITTED">Submitted</option>
        </select>
      </div>
    </div>
  );
}
