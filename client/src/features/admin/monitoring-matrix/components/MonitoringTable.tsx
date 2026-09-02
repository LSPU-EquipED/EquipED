import { useMemo, useState } from 'react';
import {
  CheckCircle,
  FilePdf,
  FileText,
  FolderOpen,
  ShieldCheck,
  User,
  Warning,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { TABLE_STYLES } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';
import { TableSkeleton } from '@/shared/components/TableSkeleton';
import { useMonitoringMatrix } from '../hooks/useMonitoringMatrix';
import type { MonitoringMatrixRow } from '../types';
import {
  formatRevisionContext,
  getRatingVariant,
  getStatusVariant,
} from '../utils';
import { MatrixFilters } from './MatrixFilters';

export function MonitoringTable() {
  const [program, setProgram] = useState('all');
  const [status, setStatus] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const { data, isLoading, isError } = useMonitoringMatrix({
    program: program !== 'all' ? program : undefined,
    status: status !== 'all' ? status : undefined,
    page,
    page_size: pageSize,
  });

  const handleProgramChange = (val: string) => {
    setProgram(val);
    setPage(1);
  };

  const handleStatusChange = (val: string) => {
    setStatus(val);
    setPage(1);
  };

  // Pagination computations
  const totalRecords = data?.total ?? data?.items?.length ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const startRecord = totalRecords > 0 ? (page - 1) * pageSize + 1 : 0;
  const endRecord = Math.min(page * pageSize, totalRecords);

  // Operational KPI metrics computed from current matrix data
  const metrics = useMemo(() => {
    const items = data?.items ?? [];
    const total = totalRecords;
    const completed = items.filter((i) =>
      i.evaluation_status.toUpperCase().startsWith('COMPLETED'),
    );
    const passingCount = completed.filter(
      (i) =>
        i.adjectival_rating === 'Very Satisfactory' ||
        i.adjectival_rating === 'Satisfactory',
    ).length;
    const passRate = completed.length > 0 ? (passingCount / completed.length) * 100 : 100;
    const flaggedItems = items.filter((i) => i.flag_count > 0);
    const totalFlags = items.reduce((sum, i) => sum + (i.flag_count || 0), 0);

    return {
      total,
      completedCount: completed.length,
      passRate: passRate.toFixed(1),
      flaggedCount: flaggedItems.length,
      totalFlags,
    };
  }, [data?.items, totalRecords]);

  return (
    <section className="space-y-6">
      {/* ── Operational KPI Summary Strip (4 Academic Metrics) ─────────── */}
      <div className="rounded-md border border-border bg-surface shadow-none divide-y sm:divide-y-0 sm:divide-x divide-border grid grid-cols-2 lg:grid-cols-4">
        {/* Total Evaluated Modules */}
        <div className="p-4 sm:p-5 flex items-center gap-3.5">
          <div className="flex size-10 sm:size-11 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
            <FolderOpen className="size-5 text-primary" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Evaluated Modules
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-7 w-14" /> : metrics.total}
            </p>
          </div>
        </div>

        {/* Quality Pass Rate */}
        <div className="p-4 sm:p-5 flex items-center gap-3.5">
          <div className="flex size-10 sm:size-11 items-center justify-center rounded-sm border border-success/30 bg-success-soft text-success shrink-0">
            <CheckCircle className="size-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Accredited Quality Rate
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-7 w-16" /> : metrics.passRate + '%'}
            </p>
          </div>
        </div>

        {/* Audit Queue (Flagged Modules) */}
        <div className="p-4 sm:p-5 flex items-center gap-3.5">
          <div className="flex size-10 sm:size-11 items-center justify-center rounded-sm border border-warning/30 bg-warning-soft text-warning shrink-0">
            <Warning className="size-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Flagged for Audit
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-7 w-14" /> : metrics.flaggedCount}
            </p>
          </div>
        </div>

        {/* Total Flagged Issues */}
        <div className="p-4 sm:p-5 flex items-center gap-3.5">
          <div className="flex size-10 sm:size-11 items-center justify-center rounded-sm border border-border bg-surface-subtle text-text shrink-0">
            <ShieldCheck className="size-5 text-primary" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Total Issue Flags
            </p>
            <p className="text-xl sm:text-2xl font-bold tracking-tight text-text tabular-nums mt-0.5">
              {isLoading ? <Skeleton className="h-7 w-14" /> : metrics.totalFlags}
            </p>
          </div>
        </div>
      </div>

      {/* ── Main Monitoring Matrix Ledger Card ─────────────────────────── */}
      <div className={TABLE_STYLES.wrapper}>
        {/* Filter Controls Bar */}
        <MatrixFilters
          program={program}
          status={status}
          onProgramChange={handleProgramChange}
          onStatusChange={handleStatusChange}
        />

        {/* Loading State */}
        {isLoading ? (
          <TableSkeleton
            ariaLabel="Loading monitoring matrix"
            columns={[
              { label: 'SLM Title', headerClassName: 'min-w-[18rem]', skeletonClassName: 'h-4 w-56' },
              { label: 'Program', skeletonClassName: 'h-5 w-20' },
              { label: 'Status', skeletonClassName: 'h-5 w-24' },
              { label: 'Form Revision', skeletonClassName: 'h-4 w-20' },
              { label: 'Rating', skeletonClassName: 'h-4 w-16' },
              { label: 'Last Updated', headerClassName: 'text-right', skeletonClassName: 'h-4 w-28 ml-auto' },
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

        {/* Empty State */}
        {!isLoading && !isError && (!data || data.items.length === 0) ? (
          <div className="py-16 text-center text-text-muted space-y-2">
            <FileText className="size-8 mx-auto text-text-muted/40" aria-hidden="true" />
            <p className="text-sm font-semibold text-text">No evaluation records yet</p>
            <p className="text-xs text-text-muted max-w-sm mx-auto">
              Evaluation runs and compliance scores will automatically populate here as faculty submit modules.
            </p>
          </div>
        ) : null}

        {/* Data Table */}
        {!isLoading && !isError && data && data.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th className={TABLE_STYLES.th}>SLM Title</th>
                  <th className={TABLE_STYLES.th}>Program</th>
                  <th className={TABLE_STYLES.th}>Status</th>
                  <th className={TABLE_STYLES.th}>Form Revision</th>
                  <th className={TABLE_STYLES.th}>Rating</th>
                  <th className={cn(TABLE_STYLES.th, 'text-right')}>Last Updated</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {data.items.map((row: MonitoringMatrixRow) => {
                  const rowKey = row.evaluation_id ?? row.matrix_id;

                  return (
                    <tr key={rowKey} className={TABLE_STYLES.tr}>
                      {/* SLM Title & Faculty Member */}
                      <td className={cn(TABLE_STYLES.td, 'font-semibold text-text max-w-[22rem]')}>
                        <div className="flex items-start gap-2.5">
                          <FilePdf className="size-4 text-primary shrink-0 mt-0.5" aria-hidden="true" />
                          <div className="min-w-0">
                            <div className="truncate font-bold" title={row.document_title || 'Untitled SLM'}>
                              {row.document_title || 'Untitled SLM'}
                            </div>
                            {row.faculty_name ? (
                              <div className="flex items-center gap-1 text-[11px] font-normal text-text-muted truncate mt-0.5">
                                <User className="size-3 text-text-muted shrink-0" aria-hidden="true" />
                                <span>Faculty: {row.faculty_name}</span>
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </td>

                      {/* Program */}
                      <td className={cn(TABLE_STYLES.td, 'text-text-muted font-medium whitespace-nowrap')}>
                        {row.program ? (
                          <span
                            className={cn(
                              'inline-flex items-center rounded-xs px-2 py-0.5 text-xs font-semibold border',
                              row.program === 'BSCS'
                                ? 'bg-primary-soft text-primary border-primary/20'
                                : 'bg-surface-subtle text-text border-border',
                            )}
                          >
                            {row.program}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>

                      {/* Evaluation Status */}
                      <td className={TABLE_STYLES.td}>
                        <Badge variant={getStatusVariant(row.evaluation_status)} withDot>
                          {row.evaluation_status.replace(/_/g, ' ')}
                        </Badge>
                      </td>

                      {/* Form Revision */}
                      <td className={cn(TABLE_STYLES.td, 'text-text-muted font-medium whitespace-nowrap font-mono text-xs')}>
                        {formatRevisionContext(row.domain_scores)}
                      </td>

                      {/* Rating */}
                      <td className={TABLE_STYLES.td}>
                        {row.adjectival_rating ? (
                          <Badge variant={getRatingVariant(row.adjectival_rating)}>
                            {row.adjectival_rating}
                          </Badge>
                        ) : (
                          <span className="text-text-muted font-medium">—</span>
                        )}
                      </td>

                      {/* Last Updated */}
                      <td className={cn(TABLE_STYLES.tdData, 'text-right text-text-muted font-medium whitespace-nowrap text-xs')}>
                        {new Date(row.last_updated).toLocaleDateString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}

        {/* ── Pagination & Record Navigation Footer ─────────────────────── */}
        {!isLoading && !isError && data && data.items.length > 0 && totalRecords > 0 ? (
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
                onClick={() => setPage((p) => Math.max(1, p - 1))}
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
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
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
