import type { UseQueryResult } from '@tanstack/react-query';
import { ChartLineUp, ClockCounterClockwise, ShieldCheck, Sparkle } from '@phosphor-icons/react';
import type { ModelValidationMetricsResponse } from '../types';
import { ConfusionMatrix } from './ConfusionMatrix';

export function ValidationPerformanceMetrics({
  metricSummary,
}: {
  metricSummary: UseQueryResult<ModelValidationMetricsResponse>;
}) {
  const completedRuns = metricSummary.data?.completed_runs ?? 0;
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
    <section aria-labelledby="validation-performance-heading" className="space-y-6">
      {/* ── Top Aggregate Performance Metrics KPI Strip ───────────────── */}
      <div className="rounded-md border border-border bg-surface shadow-none divide-y sm:divide-y-0 sm:divide-x divide-border grid grid-cols-2 lg:grid-cols-4">
        {/* Completed Runs */}
        <div className="p-4 sm:p-5 flex items-center gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
            <ClockCounterClockwise className="size-5 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Completed runs
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {completedRuns}
            </p>
          </div>
        </div>

        {/* Mean Absolute Error */}
        <div className="p-4 sm:p-5 flex items-center gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-sm border border-primary/20 bg-primary-soft text-primary shrink-0">
            <ChartLineUp className="size-5" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Mean absolute error
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {mae}
            </p>
          </div>
        </div>

        {/* Mean Latency */}
        <div className="p-4 sm:p-5 flex items-center gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
            <Sparkle className="size-5 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Mean latency
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5 font-mono">
              {latency}
            </p>
          </div>
        </div>

        {/* Mean Toxicity & Perplexity */}
        <div className="p-4 sm:p-5 flex items-center gap-3.5">
          <div className="flex size-10 items-center justify-center rounded-sm border border-success/30 bg-success-soft text-success shrink-0">
            <ShieldCheck className="size-5" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Mean toxicity
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5 font-mono">
              {toxicity}
            </p>
          </div>
        </div>
      </div>

      {/* ── Main Confusion Matrix Analytics Card ──────────────────────── */}
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

      {/* ── Provenance & Governance Notice ────────────────────────────── */}
      <div className="rounded-md border border-border bg-surface p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-text-muted">
        <div className="flex items-start gap-2 max-w-2xl">
          <ShieldCheck className="size-4 text-primary shrink-0 mt-0.5" aria-hidden="true" />
          <p className="leading-relaxed">
            <strong>Toxicity & Provenance:</strong> Reads stored agent summaries and criterion justifications. Model validation stores the resulting assessment and model provenance. Automated evaluations remain advisory; human review is authoritative.
          </p>
        </div>
        <span className="font-mono font-semibold text-text tabular-nums shrink-0">
          Perplexity: {perplexity}
        </span>
      </div>
    </section>
  );
}
