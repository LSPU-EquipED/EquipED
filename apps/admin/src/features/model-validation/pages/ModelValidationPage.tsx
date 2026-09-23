import { useState } from 'react';
import {
  ArrowsLeftRight,
  ChartLineUp,
  ClockCounterClockwise,
  Plus,
  ShieldCheck,
} from '@phosphor-icons/react';
import { Button, cn, PageContainer } from '@equiped/ui';
import { AdapterComparisonForm } from '../components/AdapterComparisonForm';
import { AgentProgressPanel } from '../components/AgentProgressPanel';
import { ValidationHistoryTable } from '../components/ValidationHistoryTable';
import { ValidationPerformanceMetrics } from '../components/ValidationPerformanceMetrics';
import { ValidationPreparationForm } from '../components/ValidationPreparationForm';
import { useAdapterComparisonFormState } from '../hooks/useAdapterComparisonFormState';
import { useModelValidationFormState } from '../hooks/useModelValidationFormState';
import {
  useModelValidationHistory,
  useModelValidationMetrics,
} from '../hooks/useModelValidationQueries';
import { terminalStatuses } from '../utils/helpers';

export type ValidationTab = 'history' | 'analytics' | 'new-run' | 'compare';

export function ModelValidationPage() {
  const [activeTab, setActiveTab] = useState<ValidationTab>('history');
  const history = useModelValidationHistory();
  const activeValidations =
    history.data?.items.filter((item) => !terminalStatuses.has(item.status)) ?? [];
  const metricSummary = useModelValidationMetrics(activeValidations.length > 0);
  const formState = useModelValidationFormState();
  const compareFormState = useAdapterComparisonFormState();

  const totalRuns = metricSummary.data?.completed_runs ?? history.data?.items.length ?? 0;
  const mae = metricSummary.data?.mean_absolute_error?.toFixed(2) ?? '—';
  const latency =
    metricSummary.data?.mean_latency_seconds != null
      ? `${metricSummary.data.mean_latency_seconds.toFixed(2)} s`
      : '—';
  const toxicity =
    metricSummary.data?.mean_toxicity_score != null
      ? `${(metricSummary.data.mean_toxicity_score * 100).toFixed(2)}%`
      : '—';

  return (
    <PageContainer as="section">
      {/* ── High-Level Workspace Navigation Tabs ───────────────────────── */}
      <div className="border-b border-border flex items-center justify-between gap-4">
        <nav className="flex items-center gap-2 overflow-x-auto" aria-label="Validation Workspaces">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'history'}
            onClick={() => setActiveTab('history')}
            className={cn(
              'flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-semibold transition-colors cursor-pointer select-none',
              activeTab === 'history'
                ? 'border-primary text-primary font-bold bg-surface'
                : 'border-transparent text-text-muted hover:text-text hover:border-border',
            )}
          >
            <ClockCounterClockwise className="size-4" />
            <span>Validation History</span>
            <span
              className={cn(
                'rounded-xs px-1.5 py-0.2 text-[10px] font-mono tabular-nums font-bold border',
                activeTab === 'history'
                  ? 'bg-primary-soft text-primary border-primary/20'
                  : 'bg-surface-subtle text-text-muted border-border',
              )}
            >
              {history.data?.items.length ?? 0}
            </span>
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'analytics'}
            onClick={() => setActiveTab('analytics')}
            className={cn(
              'flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-semibold transition-colors cursor-pointer select-none',
              activeTab === 'analytics'
                ? 'border-primary text-primary font-bold bg-surface'
                : 'border-transparent text-text-muted hover:text-text hover:border-border',
            )}
          >
            <ChartLineUp className="size-4" />
            <span>Confusion Matrix & Analytics</span>
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'new-run'}
            onClick={() => setActiveTab('new-run')}
            className={cn(
              'flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-semibold transition-colors cursor-pointer select-none',
              activeTab === 'new-run'
                ? 'border-primary text-primary font-bold bg-surface'
                : 'border-transparent text-text-muted hover:text-text hover:border-border',
            )}
          >
            <Plus className="size-4" />
            <span>New Benchmark Run</span>
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'compare'}
            onClick={() => setActiveTab('compare')}
            className={cn(
              'flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-semibold transition-colors cursor-pointer select-none',
              activeTab === 'compare'
                ? 'border-primary text-primary font-bold bg-surface'
                : 'border-transparent text-text-muted hover:text-text hover:border-border',
            )}
          >
            <ArrowsLeftRight className="size-4" />
            <span>Compare</span>
          </button>
        </nav>
      </div>

      {/* ── Tab 1: Validation History (Primary View - Above the Fold) ───── */}
      {activeTab === 'history' && (
        <div className="space-y-6">
          {/* Top KPI Metrics Bar */}
          <div className="rounded-md border border-border bg-surface shadow-none divide-y sm:divide-y-0 sm:divide-x divide-border grid grid-cols-2 lg:grid-cols-4">
            <div className="p-4 sm:p-5 flex items-center gap-3.5">
              <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
                <ClockCounterClockwise className="size-5 text-primary" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Completed Runs
                </p>
                <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
                  {totalRuns}
                </p>
              </div>
            </div>

            <div className="p-4 sm:p-5 flex items-center gap-3.5">
              <div className="flex size-10 items-center justify-center rounded-sm border border-primary/20 bg-primary-soft text-primary shrink-0">
                <ChartLineUp className="size-5" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Mean Absolute Error
                </p>
                <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
                  {mae}
                </p>
              </div>
            </div>

            <div className="p-4 sm:p-5 flex items-center gap-3.5">
              <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
                <ShieldCheck className="size-5 text-primary" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Mean Latency
                </p>
                <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
                  {latency}
                </p>
              </div>
            </div>

            <div className="p-4 sm:p-5 flex items-center gap-3.5">
              <div className="flex size-10 items-center justify-center rounded-sm border border-success/30 bg-success-soft text-success shrink-0">
                <ShieldCheck className="size-5" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Mean Toxicity
                </p>
                <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
                  {toxicity}
                </p>
              </div>
            </div>
          </div>

          {/* Active In-Flight Runs */}
          {activeValidations.map((validation) => (
            <AgentProgressPanel key={validation.validation_id} validation={validation} />
          ))}

          {/* Validation History Table - Immediate Primary View */}
          <ValidationHistoryTable history={history} />
        </div>
      )}

      {/* ── Tab 2: Confusion Matrix & Analytics View ────────────────────── */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          <ValidationPerformanceMetrics metricSummary={metricSummary} />
        </div>
      )}

      {/* ── Tab 3: Dedicated Benchmark Input Workspace ─────────────────── */}
      {activeTab === 'new-run' && (
        <div className="space-y-6">
          {activeValidations.map((validation) => (
            <AgentProgressPanel key={validation.validation_id} validation={validation} />
          ))}

          <ValidationPreparationForm form={formState} />
        </div>
      )}

      {activeTab === 'compare' && (
        <div className="space-y-6">
          {activeValidations.map((validation) => (
            <AgentProgressPanel key={validation.validation_id} validation={validation} />
          ))}

          <AdapterComparisonForm form={compareFormState} />
        </div>
      )}
    </PageContainer>
  );
}
