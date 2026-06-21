import { cn } from '@/shared/components/utils';
import type { StatusFilter } from '../hooks/useDocumentDashboard';

interface DocumentFilterBarProps {
  statusFilter: StatusFilter;
  setStatusFilter: (filter: StatusFilter) => void;
  stats: { total: number; ready: number; processing: number; failed: number };
  documentsCount: number;
  isTableReady: boolean;
}

export function DocumentFilterBar({
  statusFilter,
  setStatusFilter,
  stats,
  documentsCount,
  isTableReady,
}: DocumentFilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-6 md:px-8 py-4">
      <button
        type="button"
        onClick={() => setStatusFilter('all')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-800',
          statusFilter === 'all'
            ? 'bg-slate-800 text-white'
            : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
        )}
      >
        All
        <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-full', statusFilter === 'all' ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500')}>
          {stats.total}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('PROCESSED')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-800',
          statusFilter === 'PROCESSED'
            ? 'bg-slate-800 text-white'
            : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
        )}
      >
        Ready
        <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-full', statusFilter === 'PROCESSED' ? 'bg-white/20 text-white' : 'bg-emerald-50 text-emerald-700')}>
          {stats.ready}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('PENDING')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-800',
          statusFilter === 'PENDING'
            ? 'bg-slate-800 text-white'
            : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
        )}
      >
        Processing
        <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-full', statusFilter === 'PENDING' ? 'bg-white/20 text-white' : 'bg-amber-50 text-amber-700')}>
          {stats.processing}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('FAILED')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-800',
          statusFilter === 'FAILED'
            ? 'bg-slate-800 text-white'
            : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
        )}
      >
        Failed
        <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-full', statusFilter === 'FAILED' ? 'bg-white/20 text-white' : 'bg-red-50 text-red-700')}>
          {stats.failed}
        </span>
      </button>

      <p className="ml-auto text-xs font-semibold text-slate-400 tabular-nums whitespace-nowrap">
        {isTableReady ? `${documentsCount} of ${stats.total} shown` : 'Loading…'}
      </p>
    </div>
  );
}
