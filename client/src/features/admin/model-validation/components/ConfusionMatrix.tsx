import { useState } from 'react';
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
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const boundedValue = value == null ? 0 : Math.min(1, Math.max(0, value));
  const percentage = value == null ? null : boundedValue * 100;

  return (
    <div className="flex min-w-0 items-center gap-3 border border-slate-200 bg-slate-50 p-3">
      <div
        className="relative size-24 shrink-0"
        role="img"
        aria-label={`${label}: ${percentage == null ? 'unavailable' : `${percentage.toFixed(1)} percent`}`}
      >
        <svg className="size-24 -rotate-90" viewBox="0 0 100 100" aria-hidden="true">
          <circle cx="50" cy="50" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="butt"
            strokeDasharray={`${boundedValue * circumference} ${circumference}`}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-lg font-bold tabular-nums text-slate-900">
          {percentage == null ? '—' : `${percentage.toFixed(1)}%`}
        </span>
      </div>
      <div className="min-w-0">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-800">{label}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-600">
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
    <div className="overflow-hidden rounded-sm border border-slate-200 bg-white">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
          Score confusion matrix
        </h2>
        <p className="mt-1 text-xs text-slate-600">Expected class by predicted class</p>
      </div>
      <div className="overflow-x-auto p-4">
        {isLoading ? (
          <p className="py-16 text-center text-sm font-semibold text-slate-600">
            Loading confusion matrix…
          </p>
        ) : isError ? (
          <p className="py-16 text-center text-sm font-semibold text-[#b91c1c]">
            Unable to load validation metrics.
          </p>
        ) : (
          <div className="grid gap-5">
            <div
              className="flex flex-wrap gap-2"
              role="group"
              aria-label="Filter confusion matrix by evaluator"
            >
              {[{ id: 'all', label: 'All agents' }, ...validationAgents].map((agent) => {
                const isSelected = selectedAgent === agent.id;
                return (
                  <button
                    key={agent.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => setSelectedAgent(agent.id as 'all' | ValidationAgentId)}
                    className={cn(
                      'rounded-sm border px-3 py-2 text-xs font-bold focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
                      isSelected
                        ? 'border-[#1b3b87] bg-[#1b3b87] text-white'
                        : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-50',
                    )}
                  >
                    {agent.label}
                  </button>
                );
              })}
            </div>
            <p className="text-sm font-semibold text-slate-800" aria-live="polite">
              Showing {selectedLabel} score agreement
            </p>
            <div className="grid gap-3 md:grid-cols-3" aria-label="Confusion matrix metrics">
              <CircularMetric label="Accuracy" value={metrics.accuracy} color="#1b3b87" />
              <CircularMetric label="Precision" value={metrics.precision} color="#3b963e" />
              <CircularMetric label="Recall" value={metrics.recall} color="#3eaed4" />
            </div>
            <p className="text-xs leading-relaxed text-slate-600">
              Precision and recall are macro averages across score classes with available samples.
            </p>
            {isPerAgentBreakdownMissing ? (
              <div
                role="status"
                data-testid="per-agent-breakdown-unavailable"
                className="rounded-sm border border-slate-200 bg-slate-50 px-4 py-6 text-center"
              >
                <p className="text-sm font-bold uppercase tracking-wider text-slate-700">
                  Breakdown unavailable
                </p>
                <p className="mt-1 text-xs font-medium leading-relaxed text-slate-600">
                  {selectedLabel} has no recorded expected-vs-actual score pairs yet, so a
                  per-evaluator confusion matrix cannot be drawn. Run a validation against this
                  agent to populate it.
                </p>
              </div>
            ) : (
              <table
                className="mx-auto border-collapse text-center"
                aria-label="Score confusion matrix"
              >
                <thead>
                  <tr>
                    <th className="h-12 w-24 px-2 text-xs font-bold uppercase tracking-wider text-slate-600">
                      Expected ↓
                    </th>
                    {labels.map((label) => (
                      <th
                        key={label}
                        scope="col"
                        className="h-12 min-w-20 border border-slate-200 bg-slate-50 text-sm font-bold text-slate-800"
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
                        className="h-20 border border-slate-200 bg-slate-50 px-3 text-sm font-bold text-slate-800"
                      >
                        Expected {labels[rowIndex]}
                      </th>
                      {row.map((count, columnIndex) => {
                        const intensity = count / maximum;
                        const diagonal = rowIndex === columnIndex;
                        return (
                          <td
                            key={`${rowIndex}-${columnIndex}`}
                            className="h-20 min-w-20 border border-slate-200 text-xl font-bold tabular-nums text-slate-900"
                            style={{
                              backgroundColor: diagonal
                                ? `rgba(59, 150, 62, ${0.08 + intensity * 0.48})`
                                : `rgba(242, 200, 17, ${0.05 + intensity * 0.5})`,
                            }}
                            aria-label={`Expected ${labels[rowIndex]}, predicted ${labels[columnIndex]}: ${count}`}
                          >
                            {count}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-4 border-t border-slate-200 px-4 py-3 text-xs font-semibold text-slate-600">
        <span>
          <span className="mr-1 inline-block size-3 border border-[#3b963e] bg-[#3b963e]/30" />
          Agreement
        </span>
        <span>
          <span className="mr-1 inline-block size-3 border border-[#f2c811] bg-[#f2c811]/40" />
          Mismatch
        </span>
      </div>
    </div>
  );
}
