import { TABLE_STYLES, cn } from '@equiped/ui';
import type { HistoryRoleTab } from '../constants';
import type { HistoryEvaluationItem, EvaluationListStats } from '../types';
import { HistoryMetrics } from './HistoryMetrics';
import { HistoryFilters } from './HistoryFilters';
import { HistoryRows } from './HistoryRows';
import { HistoryPagination } from './HistoryPagination';

export interface EvaluationHistoryTableViewProps {
  allowedRoleTabs: readonly HistoryRoleTab[];
  activeRole: string;
  onRoleChange: (role: string) => void;
  status: string;
  onStatusChange: (status: string) => void;
  search: string;
  onSearchChange: (search: string) => void;
  hasActiveFilters: boolean;
  onResetFilters: () => void;
  items: HistoryEvaluationItem[];
  hasData: boolean;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  total: number;
  stats?: EvaluationListStats;
  page: number;
  pageSize: number;
  totalPages: number;
  onPageChange: (page: number | ((previousPage: number) => number)) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function EvaluationHistoryTableView({
  allowedRoleTabs,
  activeRole,
  onRoleChange,
  status,
  onStatusChange,
  search,
  onSearchChange,
  hasActiveFilters,
  onResetFilters,
  items,
  hasData,
  isLoading,
  isFetching,
  isError,
  total,
  stats,
  page,
  pageSize,
  totalPages,
  onPageChange,
  onPageSizeChange,
}: EvaluationHistoryTableViewProps) {
  return (
    <div className="space-y-6 sm:space-y-7">
      <HistoryMetrics
        isLoading={isLoading}
        hasData={hasData}
        total={total}
        stats={stats}
        items={items}
      />

      <div className={cn(TABLE_STYLES.wrapper, 'rounded-md border border-border bg-surface shadow-none overflow-hidden')}>
        <HistoryFilters
          allowedRoleTabs={allowedRoleTabs}
          activeRole={activeRole}
          onRoleChange={onRoleChange}
          status={status}
          onStatusChange={onStatusChange}
          search={search}
          onSearchChange={onSearchChange}
          hasActiveFilters={hasActiveFilters}
          onResetFilters={onResetFilters}
          isLoading={isLoading}
          isFetching={isFetching}
          hasData={hasData}
          total={total}
        />

        <div className="overflow-x-auto">
          <HistoryRows
            items={items}
            isLoading={isLoading}
            isFetching={isFetching}
            isError={isError}
            hasData={hasData}
            hasActiveFilters={hasActiveFilters}
            onResetFilters={onResetFilters}
          />
        </div>

        {!isLoading && !isError && total > 0 ? (
          <HistoryPagination
            page={page}
            pageSize={pageSize}
            totalPages={totalPages}
            total={total}
            onPageChange={onPageChange}
            onPageSizeChange={onPageSizeChange}
          />
        ) : null}
      </div>
    </div>
  );
}
