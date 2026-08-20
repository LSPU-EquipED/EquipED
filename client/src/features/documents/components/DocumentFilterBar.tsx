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
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-6 md:px-8 py-4">
      <button
        type="button"
        onClick={() => setStatusFilter('all')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
          statusFilter === 'all'
            ? 'bg-[#1b3b87] text-white'
            : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
        )}
      >
        All
        <span
          className={cn(
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
            statusFilter === 'all' ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-600',
          )}
        >
          {stats.total}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('PROCESSED')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
          statusFilter === 'PROCESSED'
            ? 'bg-[#1b3b87] text-white'
            : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
        )}
      >
        Processed
        <span
          className={cn(
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
            statusFilter === 'PROCESSED'
              ? 'bg-white/20 text-white'
              : 'bg-[#166534]/10 text-[#166534]',
          )}
        >
          {stats.ready}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('PROCESSING')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
          statusFilter === 'PROCESSING' || statusFilter === 'PENDING'
            ? 'bg-[#1b3b87] text-white'
            : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
        )}
      >
        Processing
        <span
          className={cn(
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
            statusFilter === 'PROCESSING' || statusFilter === 'PENDING'
              ? 'bg-white/20 text-white'
              : 'bg-[#f2c811]/10 text-[#1e293b]',
          )}
        >
          {stats.processing}
        </span>
      </button>

      <button
        type="button"
        onClick={() => setStatusFilter('FAILED')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
          statusFilter === 'FAILED'
            ? 'bg-[#1b3b87] text-white'
            : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
        )}
      >
        Upload Failed
        <span
          className={cn(
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
            statusFilter === 'FAILED' ? 'bg-white/20 text-white' : 'bg-[#b91c1c]/10 text-[#b91c1c]',
          )}
        >
          {stats.failed}
        </span>
      </button>

      <p className="ml-auto text-xs font-semibold text-slate-600 tabular-nums whitespace-nowrap">
        {isTableReady
          ? `${documentsCount} of ${totalFiltered ?? stats.total} shown`
          : 'Loading…'}
      </p>
    </div>
  );
}
