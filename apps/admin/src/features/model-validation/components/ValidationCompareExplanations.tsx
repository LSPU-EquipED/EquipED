import { useState } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { Button, Skeleton } from '@equiped/ui';
import { useModelValidationDetail } from '../hooks/useModelValidationQueries';
import type { ModelValidationItem } from '../types';
import { compareChipKey, type CompareChip } from '../utils/compare';

function ExplanationPanel({
  run,
  chip,
  query,
}: {
  run: ModelValidationItem;
  chip: CompareChip;
  query: UseQueryResult<ModelValidationItem>;
}) {
  const label = run.model_variant === 'base' ? 'Base' : 'Fine-tuned';
  const criterion = query.data?.criterion_scores.find(
    (score) => compareChipKey(score.agent_id, score.criterion_id) === chip.key,
  );
  const explanation = criterion?.explanation;
  const fallback = explanation?.status === 'fallback';

  return (
    <section aria-label={`${label} explanation for ${chip.label}`} className="min-w-0 space-y-3">
      <div>
        <h4 className="text-sm font-semibold text-text">{label}</h4>
        {run.model_variant === 'adapter' ? (
          <p className="mt-1 text-xs text-text-muted" title={run.adapter_id ?? undefined}>
            {run.adapter_label ?? 'Adapter version not stored.'}
          </p>
        ) : null}
      </div>

      {query.isLoading ? (
        <div role="status" aria-label={`Loading ${label} explanation`} className="space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : query.isError ? (
        <div role="alert" className="space-y-2 text-sm text-text">
          <p>Unable to load the stored explanation.</p>
          <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
            Try again
          </Button>
        </div>
      ) : (
        <>
          <p className="text-xs text-text-muted">
            {explanation?.model_name ?? 'Model name not stored.'}
          </p>
          <p className={fallback ? 'text-xs font-semibold text-warning' : 'text-xs text-text-muted'}>
            {fallback
              ? 'Fallback placeholder — not an LLM-scored result.'
              : explanation?.status === 'repaired'
                ? 'Repaired model response'
                : explanation?.status === 'ok'
                  ? 'Model-scored response'
                  : 'Generation status unavailable'}
          </p>
          <div className="space-y-1.5">
            <h5 className="text-xs font-semibold text-text">
              {fallback ? 'Stored fallback evidence' : 'Stored evidence'}
            </h5>
            {explanation?.evidence?.length ? (
              explanation.evidence.map((quote, index) => (
                <blockquote
                  key={index}
                  className="whitespace-pre-wrap rounded-sm bg-surface-subtle/50 p-3 text-sm leading-relaxed text-text [overflow-wrap:anywhere]"
                >
                  {quote}
                </blockquote>
              ))
            ) : (
              <p className="text-sm text-text-muted">Evidence not stored.</p>
            )}
          </div>
          <div className="space-y-1.5">
            <h5 className="text-xs font-semibold text-text">Captured model reasoning</h5>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-text [overflow-wrap:anywhere]">
              {fallback
                ? 'Model reasoning is unavailable for this fallback.'
                : (explanation?.reasoning ?? 'Reasoning not stored.')}
            </p>
          </div>
          {explanation?.stored_justification && (fallback || !explanation.reasoning) ? (
            <div className="space-y-1.5">
              <h5 className="text-xs font-semibold text-text">
                {fallback ? 'Fallback justification' : 'Stored justification'}
              </h5>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-text [overflow-wrap:anywhere]">
                {explanation.stored_justification}
              </p>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

function ExplanationPair({ base, adapter, chip }: ComparisonProps) {
  const baseQuery = useModelValidationDetail(base.validation_id, true);
  const adapterQuery = useModelValidationDetail(adapter.validation_id, true);
  return (
    <div className="grid min-w-0 gap-6 border-t border-border px-3 py-4 md:grid-cols-2 md:gap-8">
      <ExplanationPanel run={base} chip={chip} query={baseQuery} />
      <ExplanationPanel run={adapter} chip={chip} query={adapterQuery} />
    </div>
  );
}

interface ComparisonProps {
  base: ModelValidationItem;
  adapter: ModelValidationItem;
  chip: CompareChip;
}

export function ValidationCompareExplanations(props: ComparisonProps) {
  const [expanded, setExpanded] = useState(false);
  return (
    <details
      onToggle={(event) => setExpanded(event.currentTarget.open)}
      className="min-w-0 rounded-sm border border-border"
    >
      <summary
        aria-label={`Evidence and reasoning for ${props.chip.label}`}
        className="min-w-0 cursor-pointer rounded-sm px-3 py-2 text-xs font-semibold text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Evidence and reasoning
      </summary>
      {expanded ? <ExplanationPair {...props} /> : null}
    </details>
  );
}
