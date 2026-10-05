import { useMemo, useState } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { CheckCircle, Info, Warning } from '@phosphor-icons/react';
import { Button, Dropdown, Skeleton, TABLE_STYLES, cn } from '@equiped/ui';
import type { ModelValidationItem, ModelValidationListResponse } from '../types';
import { computePairComparison, type Side } from '../utils/compare';
import { formatTimestamp } from '../utils/helpers';

const EMPTY_ITEMS: ModelValidationItem[] = [];

const WINNER_TEXT = {
  adapter: 'Adapter is closer to the expected scores',
  base: 'Base is closer to the expected scores',
  tie: 'Tie',
} as const;

function BetterCell({
  value,
  side,
  better,
}: {
  value: string;
  side: 'base' | 'adapter';
  better: Side | null;
}) {
  const wins = better === side;
  return (
    <td
      className={cn(
        TABLE_STYLES.td,
        'text-right tabular-nums',
        wins && 'bg-success-soft font-semibold text-success',
      )}
    >
      <span className="inline-flex items-center justify-end gap-1.5">
        {wins ? (
          <span
            aria-label={`${side === 'adapter' ? 'Adapter' : 'Base'} is better`}
            className="inline-flex items-center gap-1 rounded-xs border border-success/40 px-1 text-[11px] font-semibold"
          >
            <CheckCircle className="size-3" weight="fill" aria-hidden="true" />
            Better
          </span>
        ) : null}
        {value}
      </span>
    </td>
  );
}

function runLabel(item: ModelValidationItem, suffix: string) {
  return `${item.document_title ?? 'Untitled SLM'} · ${formatTimestamp(item.created_at)} · ${suffix}`;
}

export function ValidationCompareTab({
  history,
}: {
  history: UseQueryResult<ModelValidationListResponse>;
}) {
  const items = history.data?.items ?? EMPTY_ITEMS;
  const [baseId, setBaseId] = useState('');
  const [adapterId, setAdapterId] = useState('');
  const [shown, setShown] = useState<{ baseId: string; adapterId: string } | null>(null);
  const [skipped, setSkipped] = useState<Set<string>>(() => new Set());

  const baseRuns = useMemo(
    () => items.filter((i) => i.status === 'COMPLETED' && i.model_variant === 'base'),
    [items],
  );
  const adapterRuns = useMemo(
    () => items.filter((i) => i.status === 'COMPLETED' && i.model_variant === 'adapter'),
    [items],
  );

  const baseItem = shown ? baseRuns.find((i) => i.validation_id === shown.baseId) : undefined;
  const adapterItem = shown
    ? adapterRuns.find((i) => i.validation_id === shown.adapterId)
    : undefined;
  const comparison = useMemo(
    () => (baseItem && adapterItem ? computePairComparison(baseItem, adapterItem, skipped) : null),
    [baseItem, adapterItem, skipped],
  );

  function toggleSkip(key: string) {
    setSkipped((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (history.isLoading) {
    return (
      <section
        className="space-y-3 rounded-md border border-border bg-surface p-5"
        role="status"
        aria-label="Loading validation history"
        aria-busy="true"
      >
        <Skeleton className="h-10 w-full max-w-xl" />
        <Skeleton className="h-24 w-full" />
      </section>
    );
  }

  if (history.isError) {
    return (
      <section className="rounded-md border border-border bg-destructive-soft px-4 py-10 text-center text-xs font-semibold text-destructive">
        <div className="flex items-center justify-center gap-2">
          <Warning className="size-4" aria-hidden="true" />
          Unable to load validation history.
        </div>
      </section>
    );
  }

  if (baseRuns.length === 0 || adapterRuns.length === 0) {
    return (
      <section className="rounded-md border border-border bg-surface px-4 py-14 text-center">
        <p className="text-sm font-semibold text-text">Nothing to compare yet</p>
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-text-muted">
          Comparing needs at least one completed base run and one completed adapter run. Submit
          them in the New benchmark workspace first.
        </p>
      </section>
    );
  }

  return (
    <section
      className="space-y-4 rounded-md border border-border bg-surface p-5"
      aria-labelledby="validation-compare-heading"
    >
      <div>
        <h2 id="validation-compare-heading" className="text-base font-semibold text-text">
          Compare a base run and an adapter run
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-text-muted">
          Pick one of each, then compare how close each got to the expected scores.
        </p>
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        <Dropdown
          label="Base run"
          aria-label="Base run"
          value={baseId}
          onChange={setBaseId}
          placeholder="Choose a base run"
          options={baseRuns.map((i) => ({
            value: i.validation_id,
            label: runLabel(i, 'Base'),
          }))}
          size="md"
          containerClassName="min-w-0 flex-1"
        />
        <Dropdown
          label="Adapter run"
          aria-label="Adapter run"
          value={adapterId}
          onChange={setAdapterId}
          placeholder="Choose an adapter run"
          options={adapterRuns.map((i) => ({
            value: i.validation_id,
            label: runLabel(i, i.adapter_label ?? 'adapter'),
          }))}
          size="md"
          containerClassName="min-w-0 flex-1"
        />
        <Button
          type="button"
          disabled={!baseId || !adapterId}
          onClick={() => {
            setShown({ baseId, adapterId });
            setSkipped(new Set());
          }}
        >
          Compare
        </Button>
      </div>

      {baseItem && adapterItem && baseItem.document_id !== adapterItem.document_id ? (
        <p className="flex items-start gap-2 rounded-sm border border-border bg-surface-subtle px-3 py-2 text-xs text-text-muted">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          These runs used different uploaded copies (or different SLMs). Check they are the same
          SLM.
        </p>
      ) : null}

      {comparison?.status === 'no-overlap' ? (
        <p className="text-sm text-text-muted">
          These two runs have no criteria in common with real scores, so there is nothing to
          compare.
        </p>
      ) : null}

      {comparison && comparison.status !== 'no-overlap' ? (
        <div className="space-y-4">
          {comparison.status === 'all-skipped' ? (
            <p className="text-sm text-text-muted">
              You skipped every criterion. Turn at least one back on to see the numbers.
            </p>
          ) : (
            <>
              {comparison.winner ? (
                <p
                  className={cn(
                    'rounded-sm border px-3 py-2 text-sm font-semibold',
                    comparison.winner === 'tie'
                      ? 'border-border bg-surface-subtle text-text'
                      : 'border-success/40 bg-success-soft text-success',
                  )}
                >
                  {WINNER_TEXT[comparison.winner]}
                </p>
              ) : null}
              <table className={cn(TABLE_STYLES.table, 'w-full')}>
                <thead className={TABLE_STYLES.thead}>
                  <tr>
                    <th className={TABLE_STYLES.th}>
                      <span className="sr-only">Measure</span>
                    </th>
                    <th className={cn(TABLE_STYLES.th, 'text-right')}>Base</th>
                    <th className={cn(TABLE_STYLES.th, 'text-right')}>Adapter</th>
                    <th className={cn(TABLE_STYLES.th, 'text-right')}>Result</th>
                  </tr>
                </thead>
                <tbody className={TABLE_STYLES.tbody}>
                  {comparison.rows.map((row) => (
                    <tr key={row.label}>
                      <th scope="row" className={cn(TABLE_STYLES.td, 'text-left font-medium')}>
                        {row.label}
                      </th>
                      <BetterCell value={row.base} side="base" better={row.better} />
                      <BetterCell value={row.adapter} side="adapter" better={row.better} />
                      <td className={cn(TABLE_STYLES.td, 'text-right font-semibold tabular-nums')}>
                        {row.result}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-sm font-medium text-text">{comparison.summary}</p>
            </>
          )}

          <p className="text-xs leading-relaxed text-text-muted">
            Closer to the expected scores means the model followed them. It means closer to a human
            reviewer only if the expected scores came from reviewers.
          </p>

          <div>
            <p className="text-xs font-semibold text-text">
              Skip criteria that have no real expected score
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {comparison.chips.map((chip) => (
                <button
                  key={chip.key}
                  type="button"
                  aria-pressed={chip.skipped}
                  onClick={() => toggleSkip(chip.key)}
                  className={cn(
                    'rounded-xs border px-2 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    chip.skipped
                      ? 'border-border bg-surface-subtle text-text-muted line-through'
                      : 'border-primary bg-primary-soft text-primary',
                  )}
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
