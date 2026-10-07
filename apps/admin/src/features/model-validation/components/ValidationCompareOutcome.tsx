import { TABLE_STYLES, cn } from '@equiped/ui';
import type { PairComparison } from '../utils/compare';

const WINNER_TEXT = {
  adapter: 'Adapter is closer to the expected scores',
  base: 'Base is closer to the expected scores',
  tie: 'The runs are tied',
} as const;

function ErrorBars({ base, adapter }: { base: number; adapter: number }) {
  const scale = Math.ceil(Math.max(1, base, adapter) * 2) / 2;

  return (
    <figure aria-label="Mean absolute error comparison" className="min-w-0">
      <figcaption className="mb-4 flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs">
        <span className="font-semibold text-text">Mean absolute error</span>
        <span className="text-text-muted">Lower is better</span>
      </figcaption>
      <div className="space-y-4">
        {[
          { label: 'Base', value: base, color: 'bg-text-muted' },
          { label: 'Adapter', value: adapter, color: 'bg-primary' },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="grid grid-cols-[3.5rem_minmax(0,1fr)_3rem] items-center gap-3"
          >
            <span className="text-xs font-medium text-text">{label}</span>
            <div className="h-2.5 overflow-hidden rounded-xs bg-surface-subtle" aria-hidden="true">
              <div
                className={cn('h-full rounded-xs', color)}
                style={{ width: `${(value / scale) * 100}%` }}
              />
            </div>
            <span className="text-right text-sm font-semibold tabular-nums text-text">
              {value.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
      <div
        className="ml-[4.25rem] mr-15 mt-2 flex justify-between text-[11px] tabular-nums text-text-muted"
        aria-hidden="true"
      >
        <span>0</span>
        <span>{scale.toFixed(2)}</span>
      </div>
    </figure>
  );
}

export function ValidationCompareOutcome({ comparison }: { comparison: PairComparison }) {
  const { baseMeanError, adapterMeanError } = comparison;
  if (baseMeanError == null || adapterMeanError == null) return null;
  const meanErrorChange = adapterMeanError - baseMeanError;
  const errorChangeText = Math.abs(meanErrorChange).toFixed(2);

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <div className="grid gap-6 p-4 sm:p-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-10">
        <div className="min-w-0">
          <p className="text-xs font-medium text-text-muted">Comparison outcome</p>
          <h2
            className="mt-2 max-w-md text-lg font-semibold leading-snug text-text"
            aria-live="polite"
          >
            {comparison.winner ? WINNER_TEXT[comparison.winner] : 'Comparison ready'}
          </h2>
          <p className="mt-3 text-xs text-text-muted">
            <span className="font-semibold tabular-nums text-text">{comparison.includedCount}</span>{' '}
            {comparison.includedCount === 1 ? 'criterion included' : 'criteria included'}
            {comparison.chips.length > comparison.includedCount
              ? ` · ${comparison.chips.length - comparison.includedCount} manually excluded`
              : ''}
          </p>
        </div>
        <ErrorBars base={baseMeanError} adapter={adapterMeanError} />
      </div>

      <dl
        aria-label="Adapter criterion changes"
        className="grid grid-cols-3 border-y border-border bg-surface-subtle/40"
      >
        {[
          {
            label: 'Closer',
            value: comparison.closerCount,
            color: 'text-success',
          },
          {
            label: 'Unchanged',
            value: comparison.sameCount,
            color: 'text-text',
          },
          {
            label: 'Farther',
            value: comparison.fartherCount,
            color: 'text-destructive',
          },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-3 sm:px-5"
          >
            <dt className="text-xs text-text-muted">{label}</dt>
            <dd className={cn('text-base font-semibold tabular-nums', color)}>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="overflow-x-auto">
        <table className={TABLE_STYLES.table} aria-label="Run comparison metrics">
          <thead className="border-b border-border text-xs text-text-muted">
            <tr>
              <th scope="col" className={TABLE_STYLES.th}>
                Measure
              </th>
              <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                Base
              </th>
              <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                Adapter
              </th>
              <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                Change
              </th>
            </tr>
          </thead>
          <tbody className={TABLE_STYLES.tbody}>
            {comparison.rows
              .filter((row) => row.base !== '')
              .map((row, index) => (
                <tr key={row.label}>
                  <th scope="row" className={cn(TABLE_STYLES.td, 'font-medium')}>
                    {row.label}
                  </th>
                  <td className={cn(TABLE_STYLES.td, 'text-right tabular-nums')}>{row.base}</td>
                  <td className={cn(TABLE_STYLES.td, 'text-right tabular-nums')}>{row.adapter}</td>
                  <td className={cn(TABLE_STYLES.td, 'text-right text-xs tabular-nums')}>
                    {index === 0
                      ? `${errorChangeText} ${comparison.errorVerdict === 'same' ? 'unchanged' : comparison.errorVerdict}`
                      : row.result}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-border px-4 py-3 text-xs leading-relaxed text-text-muted sm:px-5">
        Expected scores are the benchmark. Agreement with human reviewers depends on who supplied
        them.
      </p>
    </div>
  );
}
