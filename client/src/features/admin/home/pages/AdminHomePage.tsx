import { useMemo } from 'react';
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
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-6">
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
    </section>
  );
}
