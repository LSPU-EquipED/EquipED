import type { UseQueryResult } from '@tanstack/react-query';
import type { ModelValidationMetricsResponse } from '../types';
import { ConfusionMatrix } from './ConfusionMatrix';

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-4 py-3">
      <dt className="text-xs font-semibold text-slate-600">{label}</dt>
      <dd className="text-lg font-bold tabular-nums text-slate-900">{value}</dd>
    </div>
  );
}

export function ValidationPerformanceMetrics({
  metricSummary,
}: {
  metricSummary: UseQueryResult<ModelValidationMetricsResponse>;
}) {
  return (
    <section
      aria-labelledby="validation-performance-heading"
      className="grid gap-6 xl:grid-cols-[22rem_minmax(0,1fr)]"
    >
      <div className="overflow-hidden rounded-sm border border-slate-200 bg-white">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
          <h2
            id="validation-performance-heading"
            className="text-xs font-bold uppercase tracking-wider text-slate-700"
          >
            Performance metrics
          </h2>
        </div>
        <dl className="divide-y divide-slate-200">
          <MetricRow
            label="Completed runs"
            value={String(metricSummary.data?.completed_runs ?? 0)}
          />
          <MetricRow
            label="Mean absolute error"
            value={metricSummary.data?.mean_absolute_error?.toFixed(2) ?? '—'}
          />
          <MetricRow
            label="Mean latency"
            value={
              metricSummary.data?.mean_latency_seconds == null
                ? '—'
                : `${metricSummary.data.mean_latency_seconds.toFixed(2)} s`
            }
          />
          <MetricRow
            label="Score perplexity"
            value={metricSummary.data?.score_perplexity?.toFixed(2) ?? '—'}
          />
          <MetricRow
            label="Mean toxicity"
            value={
              metricSummary.data?.mean_toxicity_score == null
                ? '—'
                : `${(metricSummary.data.mean_toxicity_score * 100).toFixed(2)}%`
            }
          />
        </dl>
        <div className="grid gap-2 border-t border-slate-200 p-4 text-xs leading-relaxed text-slate-600">
          <p>
            Toxicity reads stored agent summaries and criterion justifications. Model Validation
            stores the resulting assessment and model provenance, not a duplicate comment.
          </p>
          <p>Automated evaluations remain advisory. Human review is authoritative.</p>
        </div>
      </div>

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
    </section>
  );
}
