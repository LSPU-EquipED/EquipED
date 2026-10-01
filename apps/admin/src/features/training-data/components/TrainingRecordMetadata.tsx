import { cn } from '@equiped/ui';

interface TrainingRecordMetadataProps {
  entries: readonly (readonly [label: string, value: string | number])[];
  tabularValues?: boolean;
}

export function TrainingRecordMetadata({
  entries,
  tabularValues = false,
}: TrainingRecordMetadataProps) {
  return (
    <dl className="grid gap-x-6 gap-y-3 text-[13px] leading-5 sm:grid-cols-2">
      {entries.map(([label, value]) => (
        <div key={label} className="min-w-0 space-y-0.5 border-l border-border pl-3">
          <dt className="text-text-muted">{label}</dt>
          <dd
            className={cn(
              'break-words font-medium',
              tabularValues && 'tabular-nums',
              'text-text [overflow-wrap:anywhere]',
            )}
          >
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
