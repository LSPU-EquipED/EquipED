import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';

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
        <Select value={program} onValueChange={onProgramChange}>
          <SelectTrigger>
            <SelectValue placeholder="All Programs" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Programs</SelectItem>
            <SelectItem value="BSCS">Computer Science</SelectItem>
            <SelectItem value="BSIT">Information Technology</SelectItem>
            <SelectItem value="BSEd">Education</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex-1 min-w-[200px] max-w-sm">
        <Select value={status} onValueChange={onStatusChange}>
          <SelectTrigger>
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="COMPLETED">Completed</SelectItem>
            <SelectItem value="FAILED">Failed</SelectItem>
            <SelectItem value="EVALUATING">Evaluating</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
