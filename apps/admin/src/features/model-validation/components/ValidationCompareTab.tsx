import { useMemo, useState } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { ArrowsLeftRight, Info, Warning } from '@phosphor-icons/react';
import { Button, Skeleton } from '@equiped/ui';
import type { ModelValidationItem, ModelValidationListResponse } from '../types';
import { computePairComparison } from '../utils/compare';
import { ValidationCompareCriteria } from './ValidationCompareCriteria';
import { ValidationCompareOutcome } from './ValidationCompareOutcome';
import { ValidationCompareSelection } from './ValidationCompareSelection';

const EMPTY_ITEMS: ModelValidationItem[] = [];

export function ValidationCompareTab({
  history,
  onNewBenchmark,
}: {
  history: UseQueryResult<ModelValidationListResponse>;
  onNewBenchmark?: () => void;
}) {
  const items = history.data?.items ?? EMPTY_ITEMS;
  const [baseId, setBaseId] = useState('');
  const [adapterId, setAdapterId] = useState('');
  const [shown, setShown] = useState<{
    baseId: string;
    adapterId: string;
  } | null>(null);
  const [skipped, setSkipped] = useState<Set<string>>(() => new Set());
  const baseRuns = useMemo(
    () => items.filter((item) => item.status === 'COMPLETED' && item.model_variant === 'base'),
    [items],
  );
  const adapterRuns = useMemo(
    () => items.filter((item) => item.status === 'COMPLETED' && item.model_variant === 'adapter'),
    [items],
  );
  const pending = shown !== null && (shown.baseId !== baseId || shown.adapterId !== adapterId);
  const baseItem =
    !pending && shown ? baseRuns.find((item) => item.validation_id === shown.baseId) : undefined;
  const adapterItem =
    !pending && shown
      ? adapterRuns.find((item) => item.validation_id === shown.adapterId)
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
        className="space-y-4"
        role="status"
        aria-label="Loading validation history"
        aria-busy="true"
      >
        <div className="grid gap-4 rounded-md border border-border bg-surface p-5 md:grid-cols-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
        <Skeleton className="h-44 w-full rounded-md" />
      </section>
    );
  }

  if (history.isError) {
    return (
      <section
        className="flex flex-wrap items-center justify-between gap-4 rounded-md border border-border bg-surface p-5"
        role="alert"
      >
        <p className="flex items-center gap-2 text-sm text-destructive">
          <Warning className="size-4 shrink-0" aria-hidden="true" />
          Unable to load validation history.
        </p>
        <Button variant="secondary" onClick={() => void history.refetch()}>
          Try again
        </Button>
      </section>
    );
  }

  if (baseRuns.length === 0 || adapterRuns.length === 0) {
    return (
      <section className="rounded-md border border-border bg-surface px-5 py-10 text-center">
        <ArrowsLeftRight className="mx-auto mb-3 size-6 text-primary" aria-hidden="true" />
        <p className="text-sm font-semibold text-text">Nothing to compare yet</p>
        <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-text-muted">
          Comparing needs at least one completed base run and one completed fine-tuned run. Submit them
          in the New benchmark workspace first.
        </p>
        {onNewBenchmark ? (
          <Button variant="secondary" onClick={onNewBenchmark} className="mt-4">
            New benchmark
          </Button>
        ) : null}
      </section>
    );
  }

  return (
    <section className="space-y-4" aria-label="Run comparison">
      <ValidationCompareSelection
        baseRuns={baseRuns}
        adapterRuns={adapterRuns}
        baseId={baseId}
        adapterId={adapterId}
        onBaseChange={setBaseId}
        onAdapterChange={setAdapterId}
        onCompare={() => {
          setShown({ baseId, adapterId });
          setSkipped(new Set());
        }}
      />

      {!comparison ? (
        <div
          className="rounded-md border border-dashed border-border px-5 py-8 text-center"
          role="status"
        >
          <ArrowsLeftRight className="mx-auto mb-3 size-5 text-text-muted" aria-hidden="true" />
          <p className="text-sm font-medium text-text">
            {pending
              ? 'Selections changed. Compare again to update the results.'
              : shown
                ? 'A selected run is no longer available. Choose another completed run.'
                : 'Choose two runs to compare'}
          </p>
          <p className="mt-2 text-xs text-text-muted">
            Use the same SLM and benchmark scores for a meaningful comparison.
          </p>
        </div>
      ) : (
        <>
          {baseItem && adapterItem && baseItem.document_id !== adapterItem.document_id ? (
            <p className="flex items-start gap-2 text-xs leading-relaxed text-warning" role="note">
              <Info className="size-4 shrink-0" aria-hidden="true" />
              These runs used different uploaded copies (or different SLMs). Check they are the same
              SLM.
            </p>
          ) : null}

          {comparison.differingExpected.length > 0 ? (
            <p className="text-xs leading-relaxed text-text-muted">
              {comparison.differingExpected.length}{' '}
              {comparison.differingExpected.length === 1
                ? 'criterion excluded'
                : 'criteria excluded'}
              : expected scores differ ({comparison.differingExpected.join(', ')}).
            </p>
          ) : null}

          {comparison.status === 'ok' ? (
            <ValidationCompareOutcome comparison={comparison} />
          ) : (
            <p
              className="rounded-md border border-border bg-surface px-5 py-8 text-sm text-text-muted"
              role="status"
            >
              {comparison.status === 'all-skipped'
                ? 'You excluded every criterion. Include at least one to see the comparison.'
                : 'These two runs have no criteria in common with the same expected score, so there is nothing to compare.'}
            </p>
          )}

          {baseItem && adapterItem && comparison.chips.length > 0 ? (
            <ValidationCompareCriteria
              key={`${baseItem.validation_id}:${adapterItem.validation_id}`}
              base={baseItem}
              adapter={adapterItem}
              chips={comparison.chips}
              onToggle={toggleSkip}
            />
          ) : null}
        </>
      )}
    </section>
  );
}
