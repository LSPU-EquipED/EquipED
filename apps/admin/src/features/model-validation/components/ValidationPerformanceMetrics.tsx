import type { UseQueryResult } from '@tanstack/react-query';
import { ChartLineUp, ClockCounterClockwise, ShieldCheck, Sparkle } from '@phosphor-icons/react';
import type { ModelValidationMetricsResponse } from '../types';
import { ConfusionMatrix } from './ConfusionMatrix';

function SummaryMetric({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: typeof ChartLineUp;
}) {
  return (
    <div className="flex items-start gap-3 border-r border-border px-4 py-4 last:border-r-0 sm:px-5">
      <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
      <div className="min-w-0">
        <dt className="text-xs font-medium text-text-muted">{label}</dt>
        <dd className="mt-1 text-xl font-semibold leading-none tabular-nums text-text">{value}</dd>
        <p className="mt-1.5 text-[11px] leading-relaxed text-text-muted">{detail}</p>
      </div>
    </div>
  );
}

export function ValidationPerformanceMetrics({
  metricSummary,
}: {
  metricSummary: UseQueryResult<ModelValidationMetricsResponse>;
}) {
  const mae = metricSummary.data?.mean_absolute_error?.toFixed(2) ?? '—';
  const latency =
    metricSummary.data?.mean_latency_seconds == null
      ? '—'
      : `${metricSummary.data.mean_latency_seconds.toFixed(2)} s`;
  const toxicity =
    metricSummary.data?.mean_toxicity_score == null
      ? '—'
      : `${(metricSummary.data.mean_toxicity_score * 100).toFixed(2)}%`;
  const perplexity = metricSummary.data?.score_perplexity?.toFixed(2) ?? '—';

  return (
    <section aria-label="Agreement analytics" className="space-y-5">
      <dl className="grid overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-3">
        <SummaryMetric
          icon={ChartLineUp}
          label="Mean absolute error"
          value={mae}
          detail="Distance from the expected score"
        />
        <SummaryMetric
          icon={ClockCounterClockwise}
          label="Mean latency"
          value={latency}
          detail="Average evaluation duration"
        />
        <SummaryMetric
          icon={ShieldCheck}
          label="Mean toxicity"
          value={toxicity}
          detail="Average safety signal"
        />
      </dl>

      <ConfusionMatrix
        labels={metricSummary.data?.class_labels ?? ['1', '2', '3', '4']}
        matrix={
          metricSummary.data?.confusion_matrix ?? [
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
          ]
        }
        agentMatrices={metricSummary.data?.agent_confusion_matrices}
        isLoading={metricSummary.isLoading}
        isError={metricSummary.isError}
      />

      <aside className="flex flex-col gap-3 border-t border-border pt-4 text-xs text-text-muted sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-2">
          <Sparkle className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          <p className="max-w-2xl leading-relaxed">
            Automated evaluations remain advisory. Human review is authoritative. Metrics are
            derived from stored agent summaries and criterion justifications.
          </p>
        </div>
        <dl className="flex shrink-0 gap-4 font-mono tabular-nums">
          <div>
            <dt className="font-sans text-[11px] text-text-muted">Score perplexity</dt>
            <dd className="mt-0.5 font-semibold text-text">{perplexity}</dd>
          </div>
        </dl>
      </aside>
    </section>
  );
}
