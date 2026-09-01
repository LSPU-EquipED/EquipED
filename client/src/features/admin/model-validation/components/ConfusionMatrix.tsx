import { useState } from 'react';
import { Check, WarningCircle } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import {
  calculateConfusionMatrixMetrics,
  emptyConfusionMatrix,
  hasConfusionMatrixData,
} from '../utils/confusionMatrix';
import { agentLabel, validationAgents, type ValidationAgentId } from '../utils/helpers';

function CircularMetric({
  label,
  value,
  color,
}: {
  label: string;
  value: number | null;
  color: string;
}) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const boundedValue = value == null ? 0 : Math.min(1, Math.max(0, value));
  const percentage = value == null ? null : boundedValue * 100;

  return (
    <div className="flex min-w-0 items-center gap-3.5 border border-border bg-surface p-3.5 rounded-sm shadow-none">
      <div
        className="relative size-16 shrink-0"
        role="img"
        aria-label={`${label}: ${percentage == null ? 'unavailable' : `${percentage.toFixed(1)} percent`}`}
      >
        <svg className="size-16 -rotate-90" viewBox="0 0 64 64" aria-hidden="true">
          <circle cx="32" cy="32" r={radius} fill="none" stroke="var(--border)" strokeWidth="6" />
          <circle
            cx="32"
            cy="32"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${boundedValue * circumference} ${circumference}`}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-xs font-bold tabular-nums text-text">
          {percentage == null ? '—' : `${percentage.toFixed(1)}%`}
        </span>
      </div>
      <div className="min-w-0">
        <p className="text-xs font-bold text-text uppercase tracking-wider">{label}</p>
        <p className="mt-0.5 text-[11px] leading-tight text-text-muted font-medium">
          {label === 'Accuracy' ? 'Exact score matches' : 'Macro average by score class'}
        </p>
      </div>
    </div>
  );
}

export function ConfusionMatrix({
  labels,
  matrix,
  agentMatrices,
  isLoading,
  isError,
}: {
  labels: string[];
  matrix: number[][];
  agentMatrices?: Record<string, number[][]>;
  isLoading: boolean;
  isError: boolean;
}) {
  const [selectedAgent, setSelectedAgent] = useState<'all' | ValidationAgentId>('all');
  const perAgentMatrix = selectedAgent === 'all' ? null : (agentMatrices?.[selectedAgent] ?? null);
  const isPerAgentBreakdownMissing =
    selectedAgent !== 'all' && !hasConfusionMatrixData(perAgentMatrix);
  const displayedMatrix =
    selectedAgent === 'all'
      ? matrix
      : hasConfusionMatrixData(perAgentMatrix)
        ? perAgentMatrix
        : emptyConfusionMatrix();
  const maximum = Math.max(1, ...displayedMatrix.flat());
  const metrics = calculateConfusionMatrixMetrics(displayedMatrix);
  const selectedLabel = selectedAgent === 'all' ? 'All agents' : agentLabel(selectedAgent);

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface shadow-none">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-subtle px-5 py-3.5">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-text">
            Score confusion matrix
          </h2>
          <p className="mt-0.5 text-[11px] text-text-muted">
            Expected 1–4 human benchmark class versus predicted multi-agent class
          </p>
        </div>
      </div>

      <div className="p-5 space-y-5">
        {isLoading ? (
          <p className="py-16 text-center text-xs font-semibold text-text-muted uppercase tracking-wider">
            Loading confusion matrix…
          </p>
        ) : isError ? (
          <p className="py-16 text-center text-xs font-semibold text-destructive">
            Unable to load validation metrics.
          </p>
        ) : (
          <div className="space-y-5">
            {/* Filter Buttons */}
            <div
              className="flex flex-wrap items-center gap-2"
              role="group"
              aria-label="Filter confusion matrix by evaluator"
            >
              <span className="text-xs font-semibold text-text-muted mr-1">Evaluator:</span>
              <div className="inline-flex flex-wrap items-center gap-1 rounded-sm bg-surface-subtle p-1 border border-border">
                {[{ id: 'all', label: 'All agents' }, ...validationAgents].map((agent) => {
                  const isSelected = selectedAgent === agent.id;
                  return (
                    <button
                      key={agent.id}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => setSelectedAgent(agent.id as 'all' | ValidationAgentId)}
                      className={cn(
                        'rounded-xs px-3 py-1 text-xs font-semibold transition-colors cursor-pointer select-none',
                        isSelected
                          ? 'bg-surface text-primary border border-border/80 shadow-2xs font-bold'
                          : 'text-text-muted hover:text-text border border-transparent',
                      )}
                    >
                      {agent.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Active Announcement */}
            <p className="text-xs font-semibold text-text" aria-live="polite">
              Showing {selectedLabel} score agreement
            </p>

            {/* 3 Macro Performance Meters */}
            <div className="grid gap-3 sm:grid-cols-3" aria-label="Confusion matrix metrics">
              <CircularMetric label="Accuracy" value={metrics.accuracy} color="var(--primary)" />
              <CircularMetric label="Precision" value={metrics.precision} color="var(--success)" />
              <CircularMetric label="Recall" value={metrics.recall} color="var(--info)" />
            </div>

            <p className="text-[11px] text-text-muted">
              Precision and recall are macro averages across score classes with available samples.
            </p>

            {/* Matrix Table or Missing Notice */}
            {isPerAgentBreakdownMissing ? (
              <div
                role="status"
                data-testid="per-agent-breakdown-unavailable"
                className="rounded-sm border border-border bg-surface-subtle px-4 py-8 text-center space-y-2"
              >
                <div className="flex items-center justify-center gap-2 text-warning">
                  <WarningCircle className="size-5" />
                  <p className="text-xs font-bold uppercase tracking-wider text-text">
                    Breakdown unavailable
                  </p>
                </div>
                <p className="text-xs text-text-muted max-w-md mx-auto leading-relaxed">
                  {selectedLabel} has no recorded expected-vs-actual score pairs yet, so a
                  per-evaluator confusion matrix cannot be drawn. Run a validation against this
                  agent to populate it.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto py-2">
                <table
                  className="mx-auto border-collapse text-center"
                  aria-label="Score confusion matrix"
                >
                  <thead>
                    <tr>
                      <th className="h-10 w-28 px-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted border-b border-border">
                        Expected ↓
                      </th>
                      {labels.map((label) => (
                        <th
                          key={label}
                          scope="col"
                          className="h-10 min-w-[5.5rem] border border-border bg-surface-subtle text-xs font-bold text-text"
                        >
                          Predicted {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {displayedMatrix.map((row, rowIndex) => (
                      <tr key={labels[rowIndex]}>
                        <th
                          scope="row"
                          className="h-16 border border-border bg-surface-subtle px-3 text-xs font-bold text-text"
                        >
                          Expected {labels[rowIndex]}
                        </th>
                        {row.map((count, columnIndex) => {
                          const intensity = count / maximum;
                          const diagonal = rowIndex === columnIndex;
                          return (
                            <td
                              key={`${rowIndex}-${columnIndex}`}
                              className="h-16 min-w-[5.5rem] border border-border text-base sm:text-lg font-bold tabular-nums text-text transition-colors"
                              style={{
                                backgroundColor: diagonal
                                  ? `rgba(47, 125, 50, ${0.08 + intensity * 0.42})`
                                  : count > 0
                                    ? `rgba(138, 90, 0, ${0.05 + intensity * 0.45})`
                                    : 'transparent',
                              }}
                              aria-label={`Expected ${labels[rowIndex]}, predicted ${labels[columnIndex]}: ${count}`}
                            >
                              <div className="flex flex-col items-center justify-center">
                                <span className={cn(count === 0 && 'text-text-muted/40 font-normal')}>
                                  {count}
                                </span>
                                {count > 0 ? (
                                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-text-muted/80">
                                    {diagonal ? (
                                      <>
                                        <Check className="size-2.5 text-success" />
                                        <span>match</span>
                                      </>
                                    ) : (
                                      <span>diff</span>
                                    )}
                                  </span>
                                ) : null}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer Legend */}
      <div className="flex flex-wrap items-center gap-5 border-t border-border px-5 py-3 text-xs font-semibold text-text-muted bg-surface-subtle">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-3 rounded-xs border border-success bg-success/30" />
          Agreement (Diagonal)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-3 rounded-xs border border-warning bg-warning/40" />
          Mismatch (Off-Diagonal)
        </span>
      </div>
    </div>
  );
}
