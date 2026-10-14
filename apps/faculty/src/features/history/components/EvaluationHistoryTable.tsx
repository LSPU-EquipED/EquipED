import { useHistoryViewState } from '../hooks/useHistoryViewState';
import { useMemo } from 'react';
import { Outlet } from '@tanstack/react-router';
import type { TargetAgent } from '@equiped/types';
import { HISTORY_ROLE_TABS } from '../constants';
import { useEvaluationHistory } from '../hooks/useEvaluationHistory';
import { EvaluationHistoryTableView } from './EvaluationHistoryTableView';

export interface EvaluationHistoryTableProps {
  evaluatorPermissions?: readonly string[] | null;
  userRole?: string;
  userId?: string;
}

export function EvaluationHistoryTable({
  evaluatorPermissions,
  userRole = 'faculty',
  userId,
}: EvaluationHistoryTableProps = {}) {
  const allowedRoleTabs = useMemo(() => {
    if (
      userRole === 'admin' ||
      evaluatorPermissions === undefined ||
      evaluatorPermissions === null ||
      evaluatorPermissions.length === 0
    ) {
      return HISTORY_ROLE_TABS;
    }

    return HISTORY_ROLE_TABS.filter((tab) => evaluatorPermissions.includes(tab.id));
  }, [userRole, evaluatorPermissions]);

  const defaultRole: TargetAgent = allowedRoleTabs[0]?.id ?? 'sme';
  const { status, role, search, page, pageSize, update } = useHistoryViewState(defaultRole, userId);

  const activeRole = allowedRoleTabs.some((tab) => tab.id === role) ? role : defaultRole;
  const { data, isLoading, isFetching, isError } = useEvaluationHistory({
    status: status !== 'all' ? status : undefined,
    target_agent: activeRole,
    page,
    page_size: pageSize,
  });

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const filteredItems = useMemo(() => {
    const items = data?.items ?? [];
    const query = search.trim().toLowerCase();
    if (!query) return items;

    return items.filter(
      (item) =>
        item.document_title?.toLowerCase().includes(query) ||
        item.evaluation_id.toLowerCase().includes(query),
    );
  }, [data?.items, search]);

  const hasActiveFilters = status !== 'all' || activeRole !== defaultRole || search.trim().length > 0;

  const resetFilters = () => {
    update({ status: 'all', role: defaultRole, search: '', page: 1 });
  };

  return (
    <section className="mx-auto max-w-[108rem] space-y-7 px-4 py-6 sm:px-7 sm:py-8">
      <h1 className="sr-only">Evaluation history</h1>

      <EvaluationHistoryTableView
        allowedRoleTabs={allowedRoleTabs}
        activeRole={activeRole}
        onRoleChange={(nextRole) => {
          update({ role: nextRole as TargetAgent, page: 1 });
        }}
        status={status}
        onStatusChange={(nextStatus) => {
          update({ status: nextStatus, page: 1 });
        }}
        search={search}
        onSearchChange={(search) => update({ search })}
        hasActiveFilters={hasActiveFilters}
        onResetFilters={resetFilters}
        items={filteredItems}
        hasData={Boolean(data)}
        isLoading={isLoading}
        isFetching={isFetching}
        isError={isError}
        total={total}
        stats={data?.stats}
        page={page}
        pageSize={pageSize}
        totalPages={totalPages}
        onPageChange={(nextPage) => update({ page: typeof nextPage === "function" ? nextPage(page) : nextPage })}
        onPageSizeChange={(nextPageSize) => {
          update({ pageSize: nextPageSize, page: 1 });
        }}
      />

      <Outlet />
    </section>
  );
}
