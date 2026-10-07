import { ArrowsLeftRight } from '@phosphor-icons/react';
import { Button, Dropdown } from '@equiped/ui';
import type { ModelValidationItem } from '../types';
import { formatTimestamp } from '../utils/helpers';

interface ValidationCompareSelectionProps {
  baseRuns: ModelValidationItem[];
  adapterRuns: ModelValidationItem[];
  baseId: string;
  adapterId: string;
  onBaseChange: (id: string) => void;
  onAdapterChange: (id: string) => void;
  onCompare: () => void;
}

export function ValidationCompareSelection({
  baseRuns,
  adapterRuns,
  baseId,
  adapterId,
  onBaseChange,
  onAdapterChange,
  onCompare,
}: ValidationCompareSelectionProps) {
  const selectedBase = baseRuns.find((run) => run.validation_id === baseId);
  const selectedAdapter = adapterRuns.find((run) => run.validation_id === adapterId);

  return (
    <div className="grid gap-4 rounded-md border border-border bg-surface p-4 sm:p-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
      {[
        {
          label: 'Base run',
          runs: baseRuns,
          value: baseId,
          selected: selectedBase,
          onChange: onBaseChange,
        },
        {
          label: 'Adapter run',
          runs: adapterRuns,
          value: adapterId,
          selected: selectedAdapter,
          onChange: onAdapterChange,
        },
      ].map(({ label, runs, value, selected, onChange }) => (
        <div key={label} className="min-w-0">
          <Dropdown
            label={label}
            aria-label={label}
            value={value}
            onChange={onChange}
            placeholder={`Choose a ${label.toLowerCase()}`}
            options={runs.map((run) => ({
              value: run.validation_id,
              label: run.document_title ?? 'Untitled SLM',
              description: `${formatTimestamp(run.created_at)} · ${run.adapter_label ?? (run.model_variant === 'base' ? 'Base' : 'Adapter')}`,
            }))}
            size="md"
            className="w-full"
            menuClassName="w-full"
          />
          <p className="mt-2 min-h-4 text-xs leading-4 text-text-muted">
            {selected ? (
              <>
                {formatTimestamp(selected.created_at)}
                {selected.adapter_label ? ` · ${selected.adapter_label}` : ''}
              </>
            ) : null}
          </p>
        </div>
      ))}
      <Button
        type="button"
        disabled={!selectedBase || !selectedAdapter}
        onClick={onCompare}
        className="md:mt-[22px] md:self-start"
      >
        <ArrowsLeftRight className="size-4" aria-hidden="true" />
        Compare
      </Button>
    </div>
  );
}
