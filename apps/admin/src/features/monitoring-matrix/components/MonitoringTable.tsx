import { useMemo, useState } from 'react';
import {
  CheckCircle,
  FileText,
  FolderOpen,
  MagnifyingGlass,
  ShieldCheck,
  Warning,
} from '@phosphor-icons/react';
import { Button } from '@equiped/ui';
import { Skeleton } from '@equiped/ui';
import { TABLE_STYLES } from '@equiped/ui';
import { cn } from '@equiped/ui';
import { TableSkeleton } from '@equiped/ui';
import { useMonitoringMatrix } from '../hooks/useMonitoringMatrix';
import type { MonitoringMatrixRow as MonitoringMatrixRowType } from '../types';
import { MatrixFilters } from './MatrixFilters';
import { MonitoringMatrixRow } from './MonitoringMatrixRow';

const EMPTY_ITEMS: MonitoringMatrixRowType[] = [];

export function MonitoringTable() {
  const [searchQuery, setSearchQuery] = useState('');
  const [program, setProgram] = useState('all');
  const [status, setStatus] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const trimmedSearch = searchQuery.trim();
  const { data, isLoading, isError } = useMonitoringMatrix({
    search: trimmedSearch || undefined,
    program: program !== 'all' ? program : undefined,
    status: status !== 'all' ? status : undefined,
    page,
    page_size: pageSize,
  });

  const [expandedRowIds, setExpandedRowIds] = useState<Set<string>>(new Set());

  const toggleRow = (id: string) => {
    setExpandedRowIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSearchChange = (val: string) => {
    setSearchQuery(val);
    setPage(1);
    setExpandedRowIds(new Set());
  };

  const handleProgramChange = (val: string) => {
    setProgram(val);
    setPage(1);
    setExpandedRowIds(new Set());
  };

  const handleStatusChange = (val: string) => {
    setStatus(val);
    setPage(1);
    setExpandedRowIds(new Set());
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setProgram('all');
    setStatus('all');
    setPage(1);
    setExpandedRowIds(new Set());
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    setExpandedRowIds(new Set());
  };

  // Server items and total records directly
  const items = data?.items ?? EMPTY_ITEMS;
  const totalRecords = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const startRecord = totalRecords > 0 ? (page - 1) * pageSize + 1 : 0;
  const endRecord = Math.min(page * pageSize, totalRecords);

  // Operational KPI metrics consumed directly from server response (ADR 0010)
  // Never derive rate or flags from current page items; display placeholders when unavailable
  const metrics = useMemo(() => {
    const serverMetrics = data?.metrics;
    if (serverMetrics) {
      return {
        completedCount:
          typeof serverMetrics.completed_count === 'number' && Number.isFinite(serverMetrics.completed_count)
            ? serverMetrics.completed_count
            : '—',
        passRate:
          serverMetrics.quality_pass_rate !== null && serverMetrics.quality_pass_rate !== undefined
            ? `${serverMetrics.quality_pass_rate.toFixed(1)}%`
            : '—',
        flaggedCount:
          serverMetrics.flagged_count !== null && serverMetrics.flagged_count !== undefined
            ? serverMetrics.flagged_count
            : '—',
        totalFlags:
          serverMetrics.total_flags !== null && serverMetrics.total_flags !== undefined
            ? serverMetrics.total_flags
            : '—',
      };
    }

    return {
      completedCount: '—',
      passRate: '—',
      flaggedCount: '—',
      totalFlags: '—',
    };
  }, [data?.metrics]);

  return (
    <section className="space-y-4">
      {/* ── Compact Operational Metric Ribbon (4 Academic Metrics) ─────── */}
      <div className="rounded-md border border-border bg-surface shadow-none divide-y sm:divide-y-0 sm:divide-x divide-border grid grid-cols-2 lg:grid-cols-4">
        {/* Total Evaluated Modules */}
        <div className="px-4 py-3 flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-xs border border-border bg-surface-subtle text-primary shrink-0">
            <FolderOpen className="size-4" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted truncate">
              Evaluated Modules
            </p>
            <p className="text-lg sm:text-xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-6 w-12" /> : metrics.completedCount}
            </p>
          </div>
        </div>

        {/* Quality Pass Rate */}
        <div className="px-4 py-3 flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-xs border border-success/30 bg-success-soft text-success shrink-0">
            <CheckCircle className="size-4" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted truncate">
              Quality Pass Rate
            </p>
            <p className="text-lg sm:text-xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-6 w-14" /> : metrics.passRate}
            </p>
          </div>
        </div>

        {/* Audit Queue (Flagged Modules) */}
        <div className="px-4 py-3 flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-xs border border-warning/30 bg-warning-soft text-warning shrink-0">
            <Warning className="size-4" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted truncate">
              Flagged for Audit
            </p>
            <p className="text-lg sm:text-xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-6 w-12" /> : metrics.flaggedCount}
            </p>
          </div>
        </div>

        {/* Total Flagged Issues */}
        <div className="px-4 py-3 flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-xs border border-border bg-surface-subtle text-primary shrink-0">
            <ShieldCheck className="size-4" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted truncate">
              Total Issue Flags
            </p>
            <p className="text-lg sm:text-xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-6 w-12" /> : metrics.totalFlags}
            </p>
          </div>
        </div>
      </div>

      {/* ── Standalone Filter Controls Toolbar ────────────────────────── */}
      <div className="rounded-md border border-border bg-surface px-4 py-3 sm:px-5 shadow-xs">
        <MatrixFilters
          searchQuery={searchQuery}
          onSearchChange={handleSearchChange}
          program={program}
          status={status}
          onProgramChange={handleProgramChange}
          onStatusChange={handleStatusChange}
          onResetFilters={handleResetFilters}
        />
      </div>

      {/* ── Main Monitoring Matrix Ledger Card ─────────────────────────── */}
      <div className={TABLE_STYLES.wrapper}>
        {/* Loading State */}
        {isLoading ? (
          <TableSkeleton
            ariaLabel="Loading monitoring matrix"
            columns={[
              { label: '', headerClassName: 'w-10 text-center', skeletonClassName: 'size-4 mx-auto' },
              { label: 'SLM Title', headerClassName: 'min-w-[18rem] sm:min-w-[22rem]', skeletonClassName: 'h-4 w-56' },
              { label: 'Status', headerClassName: 'w-44 min-w-[11rem]', skeletonClassName: 'h-5 w-24' },
              { label: 'Rating', headerClassName: 'w-36 min-w-[8rem]', skeletonClassName: 'h-4 w-20' },
              { label: 'Actions', headerClassName: 'text-right w-36 min-w-[8.5rem] pr-6', skeletonClassName: 'h-4 w-24 ml-auto' },
            ]}
          />
        ) : null}

        {/* Error State */}
        {isError ? (
          <div className="flex items-center justify-center py-12 px-4 text-destructive font-semibold text-sm gap-2.5 bg-destructive-soft">
            <Warning className="size-5 text-destructive shrink-0" aria-hidden="true" />
            <span>Unable to load monitoring matrix data. Please verify network connection.</span>
          </div>
        ) : null}

        {/* Empty State: No data from server (unfiltered) */}
        {!isLoading && !isError && items.length === 0 && !trimmedSearch && program === 'all' && status === 'all' ? (
          <div className="py-16 text-center text-text-muted space-y-2">
            <FileText className="size-8 mx-auto text-text-muted/40" aria-hidden="true" />
            <p className="text-sm font-semibold text-text">No evaluation records yet</p>
            <p className="text-xs text-text-muted max-w-sm mx-auto">
              Evaluation runs and compliance scores will automatically populate here as faculty submit modules.
            </p>
          </div>
        ) : null}

        {/* Search / Filter Empty State: Filtered to 0 */}
        {!isLoading && !isError && items.length === 0 && (trimmedSearch || program !== 'all' || status !== 'all') ? (
          <div className="py-16 text-center text-text-muted space-y-2">
            <MagnifyingGlass className="size-8 mx-auto text-text-muted/40" aria-hidden="true" />
            <p className="text-sm font-semibold text-text">No matching evaluation records</p>
            <p className="text-xs text-text-muted max-w-sm mx-auto">
              {trimmedSearch
                ? `No modules matched \u201c${trimmedSearch}\u201d. Try adjusting your search query or clearing filters.`
                : 'No evaluation records matched the selected filters. Try adjusting or clearing filters.'}
            </p>
            <button
              type="button"
              onClick={handleResetFilters}
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary-strong cursor-pointer"
            >
              Clear search &amp; filters
            </button>
          </div>
        ) : null}

        {/* Data Table */}
        {!isLoading && !isError && items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className="w-10 text-center py-3 pl-4 pr-1">
                    <span className="sr-only">Expand details</span>
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[18rem] sm:min-w-[22rem]')}>
                    SLM Title
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-44 min-w-[11rem]')}>
                    Status
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-36 min-w-[8rem]')}>
                    Rating
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right w-36 min-w-[8.5rem] pr-6')}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {items.map((row: MonitoringMatrixRowType) => {
                  const rowKey = row.evaluation_id ?? row.matrix_id;
                  const isExpanded = expandedRowIds.has(rowKey);

                  return (
                    <MonitoringMatrixRow
                      key={rowKey}
                      row={row}
                      isExpanded={isExpanded}
                      onToggle={() => toggleRow(rowKey)}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}

        {/* ── Pagination & Record Navigation Footer ─────────────────────── */}
        {!isLoading && !isError && items.length > 0 && totalRecords > 0 ? (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-border bg-surface px-5 py-3.5 text-xs text-text-muted">
            <div className="flex flex-wrap items-center gap-4">
              <span>
                Showing{' '}
                <strong className="font-semibold text-text tabular-nums">
                  {startRecord}–{endRecord}
                </strong>{' '}
                of <strong className="font-semibold text-text tabular-nums">{totalRecords}</strong> records
              </span>

              <div className="flex items-center gap-1.5 pl-3 border-l border-border">
                <span className="text-[11px] text-text-muted font-medium">Per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                    setExpandedRowIds(new Set());
                  }}
                  aria-label="Records per page"
                  className="h-7 border border-input bg-surface px-2 rounded-xs text-xs font-semibold text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => handlePageChange(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="h-7.5 px-3 text-xs"
              >
                Previous
              </Button>
              <span className="px-2 text-xs font-medium text-text">
                Page <strong className="font-bold tabular-nums">{page}</strong> of{' '}
                <strong className="font-bold tabular-nums">{totalPages}</strong>
              </span>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => handlePageChange(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="h-7.5 px-3 text-xs"
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
