import { useState } from 'react';
import { Check, WarningCircle } from '@phosphor-icons/react';
import { cn, Dropdown, Skeleton } from '@equiped/ui';
import {
  calculateConfusionMatrixMetrics,
  emptyConfusionMatrix,
  hasConfusionMatrixData,
} from '../utils/confusionMatrix';
import { agentLabel, validationAgents, type ValidationAgentId } from '../utils/helpers';

function MatrixMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: number | null;
  detail: string;
}) {
  return (
    <div className="px-4 py-3 sm:px-5">
      <dt className="text-xs font-medium text-text-muted">{label}</dt>
      <dd className="mt-1 text-xl font-semibold leading-none tabular-nums text-text">
        {value == null ? '—' : `${(value * 100).toFixed(1)}%`}
      </dd>
      <p className="mt-1.5 text-[11px] leading-relaxed text-text-muted">{detail}</p>
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

  const agentOptions = [{ id: 'all', label: 'All agents' }, ...validationAgents];

  return (
    <div className="min-w-0 rounded-md border border-border bg-surface">
      <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-primary">Agreement map</p>
          <h2 className="mt-1 text-lg font-semibold text-text">Score confusion matrix</h2>
          <p className="mt-1 text-sm leading-relaxed text-text-muted">
            Expected human benchmark scores compared with model predictions.
          </p>
        </div>
        <Dropdown
          value={selectedAgent}
          onChange={(value) => setSelectedAgent(value as 'all' | ValidationAgentId)}
          aria-label="Filter confusion matrix by evaluator"
          options={agentOptions.map((agent) => ({
            value: agent.id,
            label: agent.label,
          }))}
          size="md"
          align="right"
          containerClassName="w-full min-w-0 sm:w-60 sm:shrink-0"
          className="w-full"
          menuClassName="w-full"
        />
      </div>

      <div className="p-5 space-y-5">
        {isLoading ? (
          <div role="status" aria-label="Loading confusion matrix" className="space-y-5">
            <div className="grid divide-y divide-border rounded-sm border border-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="space-y-2 px-4 py-3">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-6 w-16" />
                  <Skeleton className="h-2.5 w-full" />
                </div>
              ))}
            </div>
            <div className="space-y-3 rounded-sm border border-border p-4">
              <Skeleton className="h-3 w-40" />
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-9 w-full" />
              ))}
            </div>
          </div>
        ) : isError ? (
          <p className="py-16 text-center text-xs font-semibold text-destructive">
            Unable to load validation metrics.
          </p>
        ) : (
          <div className="space-y-5">
            <p className="text-xs font-medium text-text-muted" aria-live="polite">
              Showing {selectedLabel} score agreement
            </p>

            <dl
              className="grid divide-y divide-border rounded-sm border border-border sm:grid-cols-3 sm:divide-x sm:divide-y-0"
              aria-label="Confusion matrix metrics"
            >
              <MatrixMetric
                label="Accuracy"
                value={metrics.accuracy}
                detail="Exact score matches"
              />
              <MatrixMetric
                label="Precision"
                value={metrics.precision}
                detail="Correct predicted classes"
              />
              <MatrixMetric
                label="Recall"
                value={metrics.recall}
                detail="Expected classes recovered"
              />
            </dl>

            <p className="text-[11px] leading-relaxed text-text-muted">
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
                                <span
                                  className={cn(count === 0 && 'text-text-muted/40 font-normal')}
                                >
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
      <div className="flex flex-wrap items-center gap-5 rounded-b-md border-t border-border px-5 py-3 text-xs font-semibold text-text-muted bg-surface-subtle">
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
