import { useMemo } from 'react';
import { PageContainer } from '@equiped/ui';
import { AdminKpiMetrics } from '../components/AdminKpiMetrics';
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

      {/* ── 2. Workstation Launchpads (Canonical Quick Actions) ───── */}
      <AdminQuickActions />

      {/* ── 3. Recent Evaluations Ledger Preview ────────────────────── */}
      <AdminRecentActivityTable
        recentActivity={recentActivity}
        isLoading={matrixLoading}
        isError={matrixError}
      />
    </PageContainer>
  );
}
