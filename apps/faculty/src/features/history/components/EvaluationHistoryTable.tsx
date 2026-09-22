import { useMemo, useState } from 'react';
import { Outlet } from '@tanstack/react-router';
import type { TargetAgent } from '@equiped/types';
import { HISTORY_ROLE_TABS } from '../constants';
import { useEvaluationHistory } from '../hooks/useEvaluationHistory';
import { EvaluationHistoryTableView } from './EvaluationHistoryTableView';

export interface EvaluationHistoryTableProps {
  evaluatorPermissions?: readonly string[] | null;
  userRole?: string;
}

export function EvaluationHistoryTable({
  evaluatorPermissions,
  userRole = 'faculty',
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
  const [status, setStatus] = useState('all');
  const [role, setRole] = useState<TargetAgent>(defaultRole);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

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
    setStatus('all');
    setRole(defaultRole);
    setSearch('');
    setPage(1);
  };

  return (
    <section className="mx-auto max-w-[108rem] space-y-7 px-4 py-6 sm:px-7 sm:py-8">
      <h1 className="sr-only">Evaluation history</h1>

      <EvaluationHistoryTableView
        allowedRoleTabs={allowedRoleTabs}
        activeRole={activeRole}
        onRoleChange={(nextRole) => {
          setRole(nextRole as TargetAgent);
          setPage(1);
        }}
        status={status}
        onStatusChange={(nextStatus) => {
          setStatus(nextStatus);
          setPage(1);
        }}
        search={search}
        onSearchChange={setSearch}
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
        onPageChange={setPage}
        onPageSizeChange={(nextPageSize) => {
          setPageSize(nextPageSize);
          setPage(1);
        }}
      />

      <Outlet />
    </section>
  );
}
