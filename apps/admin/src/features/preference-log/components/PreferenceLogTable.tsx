import { FileText, Warning } from '@phosphor-icons/react';
import { Button, TABLE_STYLES, TableSkeleton, cn } from '@equiped/ui';
import { usePreferenceLogTable } from '../hooks/usePreferenceLogTable';
import { PreferenceLogFilters } from './PreferenceLogFilters';
import { PreferenceLogRow } from './PreferenceLogRow';
import { PreferenceLogPagination } from './PreferenceLogPagination';

export function PreferenceLogTable() {
  const {
    logs,
    isLoading,
    isError,
    actionFilter,
    page,
    pageSize,
    expandedLogIds,
    totalRecords,
    showPagination,
    changeActionFilter,
    changePageSize,
    changePage,
    toggleExpand,
  } = usePreferenceLogTable();

  return (
    <section aria-label="Preference logs" className="space-y-4">
      <PreferenceLogFilters
        actionFilter={actionFilter}
        onFilterChange={changeActionFilter}
      />

      <div className={TABLE_STYLES.wrapper}>
        {isLoading ? (
          <TableSkeleton
            ariaLabel="Loading preference audit logs"
            columns={[
              {
                label: 'Details',
                headerClassName: 'w-14',
                cellClassName: 'w-14',
                skeletonClassName: 'size-4',
              },
              { label: 'Reviewer', skeletonClassName: 'h-4 w-32' },
              {
                label: 'Action',
                headerClassName: 'w-32',
                skeletonClassName: 'h-5 w-24',
              },
              { label: 'Evaluation', skeletonClassName: 'h-4 w-32' },
              {
                label: 'Score',
                headerClassName: 'w-20 text-right',
                skeletonClassName: 'h-4 w-6 ml-auto',
              },
              {
                label: 'Logged',
                headerClassName: 'w-40 text-right',
                skeletonClassName: 'h-4 w-28 ml-auto',
              },
            ]}
          />
        ) : isError ? (
          <div
            role="alert"
            className="flex items-center justify-center gap-2 px-4 py-12 text-sm text-destructive"
          >
            <Warning
              className="size-5 text-destructive shrink-0"
              aria-hidden="true"
            />
            <span>Unable to load preference logs. Please try again.</span>
          </div>
        ) : !logs.length ? (
          <div className="space-y-2 px-4 py-12 text-center text-sm text-text-muted">
            <FileText className="mx-auto mb-3 size-6" aria-hidden="true" />
            <p className="font-semibold text-text">
              {actionFilter === 'all'
                ? 'No preference logs yet'
                : 'No matching records'}
            </p>
            {actionFilter === 'all' ? (
              <p>Reviewer decisions and corrections will appear here.</p>
            ) : (
              <Button
                variant="secondary"
                onClick={() => changeActionFilter('all')}
              >
                Clear filter
              </Button>
            )}
          </div>
        ) : (
          <table aria-label="Preference logs" className={TABLE_STYLES.table}>
            <thead className={TABLE_STYLES.thead}>
              <tr>
                <th scope="col" className="w-14 px-2 py-3">
                  <span className="sr-only">Details</span>
                </th>
                <th scope="col" className={TABLE_STYLES.th}>
                  Reviewer
                </th>
                <th scope="col" className={cn(TABLE_STYLES.th, 'w-32')}>
                  Action
                </th>
                <th scope="col" className={TABLE_STYLES.th}>
                  Evaluation
                </th>
                <th
                  scope="col"
                  className={cn(TABLE_STYLES.th, 'w-20 text-right')}
                >
                  Score
                </th>
                <th
                  scope="col"
                  className={cn(TABLE_STYLES.th, 'w-40 text-right')}
                >
                  Logged
                </th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {logs.map((log) => (
                <PreferenceLogRow
                  key={log.log_id}
                  log={log}
                  isExpanded={expandedLogIds.has(log.log_id)}
                  onToggle={() => toggleExpand(log.log_id)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showPagination ? (
        <PreferenceLogPagination
          page={page}
          pageSize={pageSize}
          totalRecords={totalRecords}
          onPageChange={changePage}
          onPageSizeChange={changePageSize}
        />
      ) : null}
    </section>
  );
}
