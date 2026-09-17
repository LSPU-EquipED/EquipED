import { Books, CheckCircle, FileText, GraduationCap, Warning } from '@phosphor-icons/react';
import { Skeleton, cn } from '@equiped/ui';
import type { StorageRepositoryMetrics } from '../hooks/useSlmStorage';
import type { DocumentStats } from '@equiped/types';

interface StorageMetricsStripProps {
  metrics: StorageRepositoryMetrics;
  stats: DocumentStats;
  isLoading: boolean;
}

export function StorageMetricsStrip({ metrics, stats, isLoading }: StorageMetricsStripProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-3"
          >
            <div className="flex items-center justify-between gap-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="size-8 rounded-sm" />
            </div>
            <div className="space-y-1">
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-3.5 w-32" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      role="region"
      aria-label="Storage repository metrics"
    >
      {/* 1. Total Modules Card */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-3 shadow-none">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-text-muted">Course Modules</span>
          <div className="flex size-8 items-center justify-center rounded-sm bg-primary/10 text-primary border border-primary/20 shrink-0">
            <Books className="size-4" aria-hidden="true" />
          </div>
        </div>
        <div>
          <p className="text-2xl font-bold tracking-tight text-text tabular-nums">
            {(stats.total || metrics.totalModules).toLocaleString()}
          </p>
          <p className="text-xs text-text-muted mt-1 leading-normal">
            Course SLMs in repository
          </p>
        </div>
      </div>

      {/* 2. Indexed Content Card */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-3 shadow-none">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-text-muted">Indexed Content</span>
          <div className="flex size-8 items-center justify-center rounded-sm bg-info-soft text-info border border-info/20 shrink-0">
            <FileText className="size-4" aria-hidden="true" />
          </div>
        </div>
        <div>
          <p className="text-2xl font-bold tracking-tight text-text tabular-nums">
            {metrics.totalIndexedPages.toLocaleString()}{' '}
            <span className="text-xs font-normal text-text-muted">Pages</span>
          </p>
          <p className="text-xs text-text-muted mt-1 leading-normal">
            {metrics.ocrVerifiedCount > 0
              ? `${metrics.ocrVerifiedCount} with OCR text`
              : 'Native digital PDF text'}
          </p>
        </div>
      </div>

      {/* 3. Program Balance Card */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-3 shadow-none">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-text-muted">Academic Programs</span>
          <div className="flex size-8 items-center justify-center rounded-sm bg-primary/10 text-primary border border-primary/20 shrink-0">
            <GraduationCap className="size-4" aria-hidden="true" />
          </div>
        </div>
        <div>
          <p className="text-lg font-bold text-text tabular-nums pt-0.5">
            {metrics.bscsCount} <span className="text-xs font-normal text-text-muted">BSCS</span> · {metrics.bsInfoTechCount} <span className="text-xs font-normal text-text-muted">BSIT</span>
          </p>
          <p className="text-xs text-text-muted mt-1 leading-normal">
            LSPU SCC curricula
          </p>
        </div>
      </div>

      {/* 4. Ingestion Health Card */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-3 shadow-none">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-text-muted">Ingestion Health</span>
          <div
            className={cn(
              'flex size-8 items-center justify-center rounded-sm border shrink-0',
              stats.failed > 0
                ? 'bg-warning-soft border-warning/20 text-warning'
                : 'bg-success-soft border-success/20 text-success',
            )}
          >
            {stats.failed > 0 ? (
              <Warning className="size-4" aria-hidden="true" />
            ) : (
              <CheckCircle className="size-4" aria-hidden="true" />
            )}
          </div>
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold tracking-tight text-success tabular-nums">
              {stats.ready}
            </span>
            <span className="text-xs font-semibold text-success">Ready</span>
            {stats.processing > 0 && (
              <span className="text-xs font-semibold text-info tabular-nums">
                · {stats.processing} Parsing
              </span>
            )}
            {stats.failed > 0 && (
              <span className="text-xs font-semibold text-destructive tabular-nums">
                · {stats.failed} Failed
              </span>
            )}
          </div>
          <p
            className={cn(
              'text-xs mt-1 leading-normal font-normal',
              stats.failed > 0 ? 'text-warning font-medium' : 'text-text-muted',
            )}
          >
            {stats.failed > 0
              ? `${stats.failed} module${stats.failed === 1 ? '' : 's'} require attention`
              : 'All modules verified clean'}
          </p>
        </div>
      </div>
    </div>
  );
}
