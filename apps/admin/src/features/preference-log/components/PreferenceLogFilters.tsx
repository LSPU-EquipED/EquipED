import { Button } from '@equiped/ui';

const ACTION_FILTERS = [
  { id: 'all', label: 'All actions' },
  { id: 'EDIT', label: 'Edited' },
  { id: 'ACCEPT', label: 'Accepted' },
  { id: 'REJECT', label: 'Rejected' },
] as const;

interface PreferenceLogFiltersProps {
  actionFilter: string;
  onFilterChange: (filterId: string) => void;
}

export function PreferenceLogFilters({
  actionFilter,
  onFilterChange,
}: PreferenceLogFiltersProps) {
  return (
    <div
      role="group"
      aria-label="Filter by action"
      className="flex flex-wrap gap-2"
    >
      {ACTION_FILTERS.map((filter) => (
        <Button
          key={filter.id}
          type="button"
          variant={actionFilter === filter.id ? 'primary' : 'secondary'}
          aria-pressed={actionFilter === filter.id}
          onClick={() => onFilterChange(filter.id)}
        >
          {filter.label}
        </Button>
      ))}
    </div>
  );
}
