// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminRecentActivityTable } from '../AdminRecentActivityTable';
import type { MonitoringMatrixRow } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    to,
    children,
    className,
  }: {
    to: string;
    children?: React.ReactNode;
    className?: string;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

describe('AdminRecentActivityTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders COMPLETED_PARTIAL status with warning variant badge', () => {
    const rows: MonitoringMatrixRow[] = [
      {
        matrix_id: 'mat-partial',
        document_id: 'doc-partial',
        evaluation_id: 'eval-partial',
        faculty_name: 'Prof. Gomez',
        program: 'BSCS',
        document_title: 'Software Engineering Module',
        evaluation_status: 'COMPLETED_PARTIAL',
        synthesized_score: 3.45,
        domain_scores: null,
        flag_count: 1,
        feedback_status: 'NO_FEEDBACK',
        last_updated: '2026-09-02T08:00:00Z',
      },
    ];

    render(
      <AdminRecentActivityTable
        recentActivity={rows}
        isLoading={false}
        isError={false}
      />,
    );

    const badge = screen.getByText('COMPLETED PARTIAL');
    expect(badge).toBeDefined();
    // getEvaluationStatusVariant maps COMPLETED_PARTIAL to 'warning'
    expect(badge.className).toContain('bg-warning-soft');
    expect(badge.className).toContain('text-warning');
  });

  it('renders COMPLETED and FAILED statuses with respective success and destructive variant badges', () => {
    const rows: MonitoringMatrixRow[] = [
      {
        matrix_id: 'mat-completed',
        document_id: 'doc-completed',
        evaluation_id: 'eval-completed',
        faculty_name: 'Dr. Santos',
        program: 'BSIT',
        document_title: 'Networking Module',
        evaluation_status: 'COMPLETED',
        synthesized_score: 3.9,
        domain_scores: null,
        flag_count: 0,
        feedback_status: 'NO_FEEDBACK',
        last_updated: '2026-09-02T09:00:00Z',
      },
      {
        matrix_id: 'mat-failed',
        document_id: 'doc-failed',
        evaluation_id: 'eval-failed',
        faculty_name: 'Prof. Luna',
        program: 'BSCS',
        document_title: 'Databases Module',
        evaluation_status: 'FAILED',
        synthesized_score: null,
        domain_scores: null,
        flag_count: 3,
        feedback_status: 'NO_FEEDBACK',
        last_updated: '2026-09-02T10:00:00Z',
      },
    ];

    render(
      <AdminRecentActivityTable
        recentActivity={rows}
        isLoading={false}
        isError={false}
      />,
    );

    const completedBadge = screen.getByText('COMPLETED');
    expect(completedBadge.className).toContain('bg-success-soft');
    expect(completedBadge.className).toContain('text-success');

    const failedBadge = screen.getByText('FAILED');
    expect(failedBadge.className).toContain('bg-destructive-soft');
    expect(failedBadge.className).toContain('text-destructive');
  });
});
