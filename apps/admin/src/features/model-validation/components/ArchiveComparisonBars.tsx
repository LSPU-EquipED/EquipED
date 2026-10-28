interface ComparisonRow {
  label: string;
  value: number;
  display: string;
}

/** Two observations on one linear scale; exact values remain readable as text. */
export function ArchiveComparisonBars({
  label,
  rows,
  domain,
  unit = '',
}: {
  label: string;
  rows: readonly [ComparisonRow, ComparisonRow];
  domain?: readonly [number, number];
  unit?: string;
}) {
  const min = domain?.[0] ?? Math.min(0, Math.floor(Math.min(...rows.map((r) => r.value))));
  const max = domain?.[1] ?? Math.max(1, Math.ceil(Math.max(...rows.map((r) => r.value))));
  const span = max - min;
  const zero = ((0 - min) / span) * 100;

  return (
    <figure aria-label={label} className="space-y-2">
      <dl className="space-y-3">
        {rows.map((row, index) => {
          const end = ((row.value - min) / span) * 100;
          return (
            <div key={row.label} className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-3 text-xs">
                <dt className="text-text-muted">{row.label}</dt>
                <dd className="text-sm font-semibold tabular-nums text-text">{row.display}</dd>
              </div>
              <div aria-hidden="true" className="relative h-3 rounded-xs bg-surface-subtle">
                {min < 0 ? (
                  <span
                    className="absolute inset-y-0 w-px bg-border-strong"
                    style={{ left: `${zero}%` }}
                  />
                ) : null}
                <span
                  className={`absolute inset-y-0 rounded-xs ${index === 0 ? 'bg-text-muted' : 'bg-primary'}`}
                  style={{ left: `${Math.min(zero, end)}%`, width: `${Math.abs(end - zero)}%` }}
                />
              </div>
            </div>
          );
        })}
      </dl>
      <div aria-hidden="true" className="flex justify-between text-xs tabular-nums text-text-muted">
        <span>
          {min}
          {unit}
        </span>
        <span>
          {max}
          {unit}
        </span>
      </div>
    </figure>
  );
}
