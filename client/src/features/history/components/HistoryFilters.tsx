import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';

interface HistoryFiltersProps {
  status: string;
  onStatusChange: (val: string) => void;
}

export function HistoryFilters({ status, onStatusChange }: HistoryFiltersProps) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-4">
      <div className="w-full sm:w-[200px]">
        <Select value={status} onValueChange={onStatusChange}>
          <SelectTrigger>
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="COMPLETED">Completed</SelectItem>
            <SelectItem value="FAILED">Failed</SelectItem>
            <SelectItem value="EVALUATING">Evaluating</SelectItem>
            <SelectItem value="SUBMITTED">Submitted</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
