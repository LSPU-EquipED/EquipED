import { useMemo } from 'react';
import { PageContainer } from '@equiped/ui';
import { AdminKpiMetrics } from '../components/AdminKpiMetrics';
import { AdminOperationsStatus } from '../components/AdminOperationsStatus';
import { AdminQuickActions } from '../components/AdminQuickActions';
import { AdminRecentActivityTable } from '../components/AdminRecentActivityTable';
import { useAdminMatrix } from '../hooks/useAdminMatrix';
import { useAdminSummary } from '../hooks/useAdminSummary';

export function AdminHomePage() {
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useAdminSummary();
  const {
    data: matrixData,
    isLoading: matrixLoading,
    isError: matrixError,
  } = useAdminMatrix({ page_size: 5 });

  const recentActivity = useMemo(() => {
    return matrixData?.items?.slice(0, 5) ?? [];
  }, [matrixData]);

  return (
    <PageContainer as="section">
      <h1 className="sr-only">Admin workspace overview</h1>

      {/* ── 1. Top Institutional Metrics Strip ───────────────────────── */}
      <AdminKpiMetrics
        summary={summary}
        isLoading={summaryLoading}
        isError={summaryError}
      />

      {/* ── 2. Main Workstation Area: Split Ledger + Launchpads ───── */}
      <div className="grid min-w-0 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0 space-y-6">
          <AdminOperationsStatus summary={summary} isLoading={summaryLoading} isError={summaryError} />
          <AdminRecentActivityTable
            recentActivity={recentActivity}
            isLoading={matrixLoading}
            isError={matrixError}
          />
        </div>
        <AdminQuickActions />
      </div>
    </PageContainer>
  );
}
