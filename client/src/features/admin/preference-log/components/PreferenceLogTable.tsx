import { useState } from 'react';
import { BookOpen, FileText, ShieldCheck, Spinner, Warning } from '@phosphor-icons/react';
import { TABLE_STYLES } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';
import { usePreferenceLogs } from '../hooks/usePreferenceLogs';
import type { PreferenceLogItem } from '../types';
import { PreferenceLogFilters } from './PreferenceLogFilters';
import { PreferenceLogRow } from './PreferenceLogRow';
import { PreferenceLogPagination } from './PreferenceLogPagination';

export function PreferenceLogTable() {
  const [actionFilter, setActionFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [expandedLogIds, setExpandedLogIds] = useState<Set<string>>(new Set());

  const { data, isLoading, isError } = usePreferenceLogs({
    action: actionFilter !== 'all' ? actionFilter : undefined,
    page,
    page_size: pageSize,
  });

  const toggleExpand = (logId: string) => {
    setExpandedLogIds((prev) => {
      const next = new Set(prev);
      if (next.has(logId)) next.delete(logId);
      else next.add(logId);
      return next;
    });
  };

  const totalRecords = data?.total ?? data?.items?.length ?? 0;

  return (
    <section className="space-y-5">
      <PreferenceLogFilters
        actionFilter={actionFilter}
        onFilterChange={(filterId) => {
          setActionFilter(filterId);
          setPage(1);
        }}
        totalRecords={totalRecords}
      />

      <div className={TABLE_STYLES.wrapper}>
        <div className="flex items-center justify-between border-b border-border bg-surface-subtle px-5 py-3.5">
          <div className="flex items-center gap-2">
            <BookOpen className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-text">
              Reviewer Preference & Override Audit Log
            </h2>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-text-muted uppercase tracking-wider">
            <ShieldCheck className="size-3.5 text-primary" />
            <span>Authoritative Human Governance</span>
          </div>
        </div>

        {isLoading ? (
          <div className="flex flex-col items-center justify-center gap-2.5 py-16 text-text-muted font-medium text-sm">
            <Spinner className="size-5 animate-spin text-primary" />
            <span className="text-xs font-semibold uppercase tracking-wider">
              Loading preference audit logs…
            </span>
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center py-12 px-4 text-destructive font-semibold text-sm gap-2.5 bg-destructive-soft">
            <Warning className="size-5 text-destructive shrink-0" aria-hidden="true" />
            <span>Failed to load preference logs from server.</span>
          </div>
        ) : !data?.items.length ? (
          <div className="py-16 text-center text-text-muted space-y-1.5">
            <FileText className="size-8 text-text-muted/40 mx-auto" aria-hidden="true" />
            <p className="text-sm font-semibold text-text">No preference audit logs recorded yet.</p>
            <p className="text-xs text-text-muted max-w-sm mx-auto">
              Faculty score overrides and justification edits submitted during interactive evaluations will automatically appear here.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th className="py-3 px-3 w-10 text-center" />
                  <th className={cn(TABLE_STYLES.th, 'w-48')}>Reviewer User ID</th>
                  <th className={cn(TABLE_STYLES.th, 'w-32')}>Action</th>
                  <th className={cn(TABLE_STYLES.th, 'w-48')}>Evaluation ID</th>
                  <th className={cn(TABLE_STYLES.th, 'w-auto')}>Details / Score</th>
                  <th className={cn(TABLE_STYLES.th, 'w-48 text-right')}>Logged Timestamp</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {data.items.map((log: PreferenceLogItem) => (
                  <PreferenceLogRow
                    key={log.log_id}
                    log={log}
                    isExpanded={expandedLogIds.has(log.log_id)}
                    onToggle={() => toggleExpand(log.log_id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!isLoading && !isError && data && data.items.length > 0 && totalRecords > 0 ? (
          <PreferenceLogPagination
            page={page}
            pageSize={pageSize}
            totalRecords={totalRecords}
            onPageChange={setPage}
            onPageSizeChange={(newPageSize) => {
              setPageSize(newPageSize);
              setPage(1);
            }}
          />
        ) : null}
      </div>
    </section>
  );
}
