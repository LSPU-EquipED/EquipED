import { cn } from '@/shared/components/utils';

interface DocumentPaginationProps {
  page: number;
  setPage: (page: number | ((prev: number) => number)) => void;
  pageSize: number;
  setPageSize: (size: number) => void;
  totalPages: number;
}

export function DocumentPagination({
  page,
  setPage,
  pageSize,
  setPageSize,
  totalPages,
}: DocumentPaginationProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 bg-slate-50/30 px-6 md:px-8 py-4">
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500 font-bold uppercase tracking-wider">Show</span>
        <select
          value={pageSize}
          onChange={(e) => {
            setPageSize(Number(e.target.value));
            setPage(1);
          }}
          className="h-8 border border-slate-200 bg-white px-2 focus:outline-none focus:ring-2 focus:ring-slate-800 rounded-sm text-xs font-bold text-slate-700 cursor-pointer"
        >
          <option value={10}>10 rows</option>
          <option value={25}>25 rows</option>
          <option value={50}>50 rows</option>
        </select>
      </div>

      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider tabular-nums">
        Page {page} of {totalPages}
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          disabled={page === 1}
          onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
          className="inline-flex h-8 items-center justify-center border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:hover:bg-white text-slate-700 px-3 rounded-sm text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-800"
        >
          Previous
        </button>
        
        {Array.from({ length: totalPages }).map((_, idx) => {
          const p = idx + 1;
          const isCurrent = p === page;
          
          if (totalPages > 5 && p !== 1 && p !== totalPages && Math.abs(p - page) > 1) {
            if (p === 2 && page > 3) {
              return <span key="dots-start" className="px-1 text-slate-400 text-xs font-bold select-none">...</span>;
            }
            if (p === totalPages - 1 && page < totalPages - 2) {
              return <span key="dots-end" className="px-1 text-slate-400 text-xs font-bold select-none">...</span>;
            }
            return null;
          }

          return (
            <button
              key={p}
              type="button"
              onClick={() => setPage(p)}
              className={cn(
                'inline-flex size-8 items-center justify-center rounded-sm text-xs font-bold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-800',
                isCurrent
                  ? 'bg-slate-800 text-white'
                  : 'border border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
              )}
            >
              {p}
            </button>
          );
        })}

        <button
          type="button"
          disabled={page === totalPages}
          onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
          className="inline-flex h-8 items-center justify-center border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:hover:bg-white text-slate-700 px-3 rounded-sm text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-800"
        >
          Next
        </button>
      </div>
    </div>
  );
}
