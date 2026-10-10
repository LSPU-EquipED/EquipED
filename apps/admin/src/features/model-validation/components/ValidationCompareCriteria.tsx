import { CaretDown } from '@phosphor-icons/react';
import { cn } from '@equiped/ui';
import type { ModelValidationItem } from '../types';
import { compareChipKey, type CompareChip } from '../utils/compare';

interface ValidationCompareCriteriaProps {
  base: ModelValidationItem;
  adapter: ModelValidationItem;
  chips: CompareChip[];
  onToggle: (key: string) => void;
}

export function ValidationCompareCriteria({
  base,
  adapter,
  chips,
  onToggle,
}: ValidationCompareCriteriaProps) {
  const baseScores = new Map(
    base.criterion_scores.map((score) => [
      compareChipKey(score.agent_id, score.criterion_id),
      score,
    ]),
  );
  const adapterScores = new Map(
    adapter.criterion_scores.map((score) => [
      compareChipKey(score.agent_id, score.criterion_id),
      score,
    ]),
  );
  const included = chips.filter((chip) => !chip.skipped).length;

  return (
    <details className="group rounded-md border border-border bg-surface">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-md px-4 py-4 text-sm font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:px-5 [&::-webkit-details-marker]:hidden">
        <span>Criterion details</span>
        <span className="flex items-center gap-3 text-xs font-normal text-text-muted">
          <span className="tabular-nums">
            {included} of {chips.length} included
          </span>
          <CaretDown
            className="size-4 transition-transform duration-150 group-open:rotate-180 motion-reduce:transition-none"
            aria-hidden="true"
          />
        </span>
      </summary>
      <div className="border-t border-border">
        <p className="px-4 py-3 text-xs leading-relaxed text-text-muted sm:px-5">
          Include only criteria with a meaningful expected score. Changes update the comparison
          immediately.
        </p>
        <div className="hidden grid-cols-[minmax(0,1fr)_4rem_4rem_4rem] gap-4 border-y border-border bg-surface-subtle/40 px-5 py-2 text-right text-xs text-text-muted sm:grid">
          <span className="text-left">Criterion / include</span>
          <span>Expected</span>
          <span>Base</span>
          <span>Fine-tuned</span>
        </div>
        <div className="divide-y divide-border">
          {chips.map((chip) => {
            const score = baseScores.get(chip.key);
            const adapterScore = adapterScores.get(chip.key);
            return (
              <div
                key={chip.key}
                className={cn(
                  'grid gap-3 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_4rem_4rem_4rem] sm:items-center sm:gap-4 sm:px-5',
                  chip.skipped && 'bg-surface-subtle/30',
                )}
              >
                <label className="flex min-w-0 cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    checked={!chip.skipped}
                    onChange={() => onToggle(chip.key)}
                    aria-label={`Include ${chip.label}`}
                    className="mt-0.5 size-4 shrink-0 cursor-pointer accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  />
                  <span className="min-w-0">
                    <span className="block text-xs text-text-muted">{chip.label}</span>
                    <span className="mt-0.5 block text-sm leading-snug text-text">
                      {score?.criterion_title ?? chip.label}
                    </span>
                  </span>
                </label>
                <div className="grid grid-cols-3 gap-3 pl-7 sm:contents">
                  {[
                    { label: 'Expected', value: score?.expected_score },
                    { label: 'Base', value: score?.actual_score },
                    { label: 'Fine-tuned', value: adapterScore?.actual_score },
                  ].map(({ label, value }) => (
                    <dl key={label} className="text-sm tabular-nums text-text sm:text-right">
                      <dt className="text-xs text-text-muted sm:sr-only">{label}</dt>
                      <dd>{value ?? '—'}</dd>
                    </dl>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </details>
  );
}
