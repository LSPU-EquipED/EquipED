import { cn } from '@/shared/components/utils';
import type { DocumentStats } from '@/shared/types/documents';
import type { StatusFilter } from '../hooks/useDocumentDashboard';

interface DocumentFilterBarProps {
  statusFilter: StatusFilter;
  setStatusFilter: (status: StatusFilter) => void;
  stats: DocumentStats;
  documentsCount: number;
  totalFiltered?: number;
  isTableReady: boolean;
}

export function DocumentFilterBar({
  statusFilter,
  setStatusFilter,
  stats,
  documentsCount,
  totalFiltered,
  isTableReady,
}: DocumentFilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border bg-surface px-6 md:px-8 py-4">
      <button
        type="button"
        onClick={() => setStatusFilter('all')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          statusFilter === 'all'
            ? 'bg-primary text-primary-foreground'
            : 'border border-border bg-surface text-text hover:bg-surface-subtle',
        )}
      >
        All
        <span
          className={cn(
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
            statusFilter === 'all'
              ? 'bg-primary-foreground/20 text-primary-foreground'
              : 'bg-surface-subtle text-text-muted border border-border/50',
          )}
        >
          {stats.total}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('PROCESSED')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          statusFilter === 'PROCESSED'
            ? 'bg-primary text-primary-foreground'
            : 'border border-border bg-surface text-text hover:bg-surface-subtle',
        )}
      >
        Processed
        <span
          className={cn(
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
            statusFilter === 'PROCESSED'
              ? 'bg-primary-foreground/20 text-primary-foreground'
              : 'bg-success-soft text-success border border-success/20',
          )}
        >
          {stats.ready}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('PROCESSING')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          statusFilter === 'PROCESSING' || statusFilter === 'PENDING'
            ? 'bg-primary text-primary-foreground'
            : 'border border-border bg-surface text-text hover:bg-surface-subtle',
        )}
      >
        Processing
        <span
          className={cn(
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
            statusFilter === 'PROCESSING' || statusFilter === 'PENDING'
              ? 'bg-primary-foreground/20 text-primary-foreground'
              : 'bg-warning-soft text-warning border border-warning/20',
          )}
        >
          {stats.processing}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('FAILED')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          statusFilter === 'FAILED'
            ? 'bg-primary text-primary-foreground'
            : 'border border-border bg-surface text-text hover:bg-surface-subtle',
        )}
      >
        Upload Failed
        <span
          className={cn(
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
            statusFilter === 'FAILED'
              ? 'bg-primary-foreground/20 text-primary-foreground'
              : 'bg-destructive-soft text-destructive border border-destructive/20',
          )}
        >
          {stats.failed}
        </span>
      </button>

      <p className="ml-auto text-xs font-semibold text-text-muted tabular-nums whitespace-nowrap">
        {isTableReady
          ? `${documentsCount} of ${totalFiltered ?? stats.total} shown`
          : 'Loading…'}
      </p>
    </div>
  );
}
