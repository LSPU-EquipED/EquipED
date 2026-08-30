import { useNavigate } from '@tanstack/react-router';
import { useMemo } from 'react';
import { AlertTriangle, ArrowRight, Plus, ScanSearch, Upload } from 'lucide-react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES, TYPOGRAPHY, type StatusVariant } from '@/shared/constants/theme';
import { useAdminMatrix } from '../hooks/useAdminMatrix';
import { useAdminSummary } from '../hooks/useAdminSummary';
import type { MonitoringMatrixRow } from '../types';

function getStatusVariant(status: string): StatusVariant {
  if (status === 'FAILED') return 'destructive';
  if (status.startsWith('COMPLETED')) return 'success';
  if (status === 'EVALUATING') return 'info';
  return 'warning';
}

export function AdminHomePage() {
  const navigate = useNavigate();
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useAdminSummary();
  const {
    data: matrixData,
    isLoading: matrixLoading,
    isError: matrixError,
  } = useAdminMatrix({ page_size: 5 });

  const recentActivity = useMemo(() => {
    return matrixData?.items?.slice(0, 5) ?? [];
  }, [matrixData]);

  return (
    <section className="grid gap-8">
      {/* Summary Row */}
      <div className="border border-border bg-surface rounded-md overflow-hidden">
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-border">
          <SummaryItem
            label="Total SLMs"
            value={summary?.total_documents ?? 0}
            isLoading={summaryLoading}
            isError={summaryError}
          />
          <SummaryItem
            label="Active Evaluations"
            value={summary?.active_evaluations ?? 0}
            isLoading={summaryLoading}
            isError={summaryError}
          />
          <SummaryItem
            label="Registered Faculty"
            value={summary?.total_faculty ?? 0}
            isLoading={summaryLoading}
            isError={summaryError}
          />
          <SummaryItem
            label="Failed Evaluations"
            value={summary?.failed_evaluations ?? 0}
            isLoading={summaryLoading}
            isError={summaryError}
            variant="destructive"
          />
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-sm bg-primary-soft border border-primary/20 text-primary shrink-0">
              <Plus className="size-5" />
            </div>
            <div>
              <p className="font-semibold text-text">Create Faculty Account</p>
              <p className="text-xs text-text-muted mt-1 leading-relaxed">
                Add a new faculty member to the system.
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full justify-between uppercase tracking-wider font-semibold text-xs"
            onClick={() => navigate({ to: '/admin/users' })}
          >
            <span>Go to user management</span>
            <ArrowRight className="size-4 text-text-muted" />
          </Button>
        </div>

        <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-sm bg-primary-soft border border-primary/20 text-primary shrink-0">
              <ScanSearch className="size-5" />
            </div>
            <div>
              <p className="font-semibold text-text">Validate Model Scores</p>
              <p className="text-xs text-text-muted mt-1 leading-relaxed">
                Compare an SLM evaluation with a human expected score.
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full justify-between uppercase tracking-wider font-semibold text-xs"
            onClick={() => navigate({ to: '/admin/model-validation' })}
          >
            <span>Open model validation</span>
            <ArrowRight className="size-4 text-text-muted" />
          </Button>
        </div>

        <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-sm bg-primary-soft border border-primary/20 text-primary shrink-0">
              <Upload className="size-5" />
            </div>
            <div>
              <p className="font-semibold text-text">Upload Reference Document</p>
              <p className="text-xs text-text-muted mt-1 leading-relaxed">
                Ingest syllabi, rubrics, or curricula.
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full justify-between uppercase tracking-wider font-semibold text-xs"
            onClick={() => navigate({ to: '/admin/ingest' })}
          >
            <span>Go to ingestion</span>
            <ArrowRight className="size-4 text-text-muted" />
          </Button>
        </div>

        <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-sm bg-warning-soft border border-warning/20 text-warning shrink-0">
              <AlertTriangle className="size-5" />
            </div>
            <div>
              <p className="font-semibold text-text">Review Failures</p>
              <p className="text-xs text-text-muted mt-1 leading-relaxed">
                Check failed evaluations in the matrix.
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full justify-between uppercase tracking-wider font-semibold text-xs"
            onClick={() => navigate({ to: '/matrix' })}
          >
            <span>Open monitoring matrix</span>
            <ArrowRight className="size-4 text-text-muted" />
          </Button>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="space-y-4">
        <div className="flex items-end justify-between">
          <div>
            <p className={TYPOGRAPHY.labelMuted}>
              Recent Activity
            </p>
            <h2 className={cn(TYPOGRAPHY.headingMd, 'mt-1')}>Latest Evaluations</h2>
          </div>
          <button
            type="button"
            className="inline-flex items-center justify-center text-xs font-semibold text-primary hover:underline uppercase tracking-wider transition-colors cursor-pointer"
            onClick={() => navigate({ to: '/matrix' })}
          >
            <span>View all</span>
            <ArrowRight className="ml-1 size-4" />
          </button>
        </div>

        <div className={TABLE_STYLES.wrapper}>
          {matrixLoading ? (
            <div className="space-y-2.5 p-5">
              <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
              <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
              <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            </div>
          ) : matrixError ? (
            <div className="py-12 text-center">
              <p className="text-sm text-destructive font-semibold">
                Unable to load recent activity.
              </p>
              <p className="text-xs text-text-muted mt-1 font-medium">
                Please try refreshing the page.
              </p>
            </div>
          ) : recentActivity.length === 0 ? (
            <div className="py-12 text-center text-text-muted font-medium text-sm">
              <p>No recent evaluation activity.</p>
            </div>
          ) : (
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th className={TABLE_STYLES.th}>SLM Title</th>
                  <th className={TABLE_STYLES.th}>Program</th>
                  <th className={TABLE_STYLES.th}>Status</th>
                  <th className={cn(TABLE_STYLES.th, 'text-right')}>Score</th>
                  <th className={cn(TABLE_STYLES.th, 'text-right')}>Flags</th>
                  <th className={cn(TABLE_STYLES.th, 'text-right')}>Updated</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {recentActivity.map((row: MonitoringMatrixRow) => (
                  <tr key={row.evaluation_id} className={TABLE_STYLES.tr}>
                    <td className={cn(TABLE_STYLES.td, 'font-semibold text-text')}>
                      {row.document_title || 'Untitled SLM'}
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-text-muted font-medium')}>
                      {row.program || '—'}
                    </td>
                    <td className={TABLE_STYLES.td}>
                      <Badge variant={getStatusVariant(row.evaluation_status)} withDot>
                        {row.evaluation_status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-right text-text font-medium')}>
                      {row.synthesized_score != null ? row.synthesized_score.toFixed(2) : '—'}
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-right')}>
                      {row.flag_count > 0 ? (
                        <span className="inline-flex items-center justify-center min-w-5 h-5 rounded-full bg-accent-soft text-accent-foreground text-xs font-bold px-1.5 border border-accent/30 tabular-nums">
                          {row.flag_count}
                        </span>
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-right text-text-muted font-medium')}>
                      {new Date(row.last_updated).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
}

interface SummaryItemProps {
  label: string;
  value: number;
  isLoading: boolean;
  isError: boolean;
  variant?: 'default' | 'destructive';
}

function SummaryItem({ label, value, isLoading, isError, variant = 'default' }: SummaryItemProps) {
  return (
    <div className="px-5 py-4">
      <p className={TYPOGRAPHY.labelMuted}>{label}</p>
      <div className="mt-1.5">
        {isLoading ? (
          <div className="animate-pulse bg-surface-subtle h-7 w-12 rounded-sm" />
        ) : isError ? (
          <p className="text-sm font-semibold text-destructive">Failed</p>
        ) : (
          <p
            className={cn(
              'text-2xl font-bold tabular-nums',
              variant === 'destructive' && value > 0 ? 'text-destructive' : 'text-text'
            )}
          >
            {value}
          </p>
        )}
      </div>
    </div>
  );
}
