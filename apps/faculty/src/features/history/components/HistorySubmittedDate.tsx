import { cn } from '@equiped/ui';
import { formatSubmittedDate } from '../utils/historyFormatters';

export function HistorySubmittedDate({
  value,
  compact = false,
}: {
  value: string;
  compact?: boolean;
}) {
  const date = formatSubmittedDate(value);
  return (
    <time dateTime={value} aria-label={date} className="tabular-nums">
      <span
        className={cn(
          'block',
          compact ? 'text-xs text-text-muted' : 'text-sm text-text',
        )}
      >
        {date}
      </span>
    </time>
  );
}
