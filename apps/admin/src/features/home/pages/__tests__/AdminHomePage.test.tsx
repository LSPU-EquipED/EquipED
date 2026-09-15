// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { UseQueryResult } from '@tanstack/react-query';
import React from 'react';
import { AdminHomePage } from '../AdminHomePage';
import * as useAdminSummaryModule from '../../hooks/useAdminSummary';
import * as useAdminMatrixModule from '../../hooks/useAdminMatrix';
import type { MatrixListResponse, MonitoringMatrixRow, SystemSummaryResponse } from '../../types';

const mockNavigate = vi.fn();

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mockNavigate,
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

const mockSummary: SystemSummaryResponse = {
  total_documents: 42,
  active_evaluations: 3,
  total_faculty: 15,
  failed_evaluations: 1,
};

const mockMatrixRows: MonitoringMatrixRow[] = [
  {
    matrix_id: 'matrix-1',
    document_id: 'doc-1',
    evaluation_id: 'eval-1',
    faculty_name: 'Prof. Cruz',
    program: 'BSIT',
    document_title: 'IT101 Module 1',
    evaluation_status: 'COMPLETED',
    synthesized_score: 3.85,
    domain_scores: null,
    flag_count: 0,
    feedback_status: 'NO_FEEDBACK',
    last_updated: '2026-09-01T10:00:00Z',
  },
  {
    matrix_id: 'matrix-2',
    document_id: 'doc-2',
    evaluation_id: 'eval-2',
    faculty_name: 'Dr. Santos',
    program: 'BSCS',
    document_title: 'CS201 Algorithms',
    evaluation_status: 'FAILED',
    synthesized_score: null,
    domain_scores: null,
    flag_count: 2,
    feedback_status: 'NO_FEEDBACK',
    last_updated: '2026-09-01T11:00:00Z',
  },
];

describe('AdminHomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders summary metrics correctly when loaded', () => {
    vi.spyOn(useAdminSummaryModule, 'useAdminSummary').mockReturnValue({
      data: mockSummary,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<SystemSummaryResponse>);

    vi.spyOn(useAdminMatrixModule, 'useAdminMatrix').mockReturnValue({
      data: { items: mockMatrixRows, total: 2, page: 1, page_size: 5 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse>);

    render(<AdminHomePage />);

    expect(screen.getByText('Total SLMs Processed')).toBeDefined();
    expect(screen.getByText('42')).toBeDefined();
    expect(screen.getByText('Active Evaluations')).toBeDefined();
    expect(screen.getByText('3')).toBeDefined();
    expect(screen.getByText('Registered Faculty')).toBeDefined();
    expect(screen.getByText('15')).toBeDefined();
    expect(screen.getByText('Failed Evaluations')).toBeDefined();
    expect(screen.getByText('1')).toBeDefined();
  });

  it('provides canonical quick action buttons that navigate to appropriate pages', () => {
    vi.spyOn(useAdminSummaryModule, 'useAdminSummary').mockReturnValue({
      data: mockSummary,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<SystemSummaryResponse>);

    vi.spyOn(useAdminMatrixModule, 'useAdminMatrix').mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 5 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse>);

    render(<AdminHomePage />);

    // Canonical quick actions required by openspec/specs/admin-home/spec.md
    const createFacultyBtn = screen.getByRole('button', { name: /create faculty account/i });
    expect(createFacultyBtn).toBeDefined();
    fireEvent.click(createFacultyBtn);
    expect(mockNavigate).toHaveBeenCalledWith({ to: '/admin/users' });

    const uploadRefBtn = screen.getByRole('button', { name: /upload reference document/i });
    expect(uploadRefBtn).toBeDefined();
    fireEvent.click(uploadRefBtn);
    expect(mockNavigate).toHaveBeenCalledWith({ to: '/admin/ingest' });

    // Additional workstation actions
    const validateModelBtn = screen.getByRole('button', { name: /validate model/i });
    fireEvent.click(validateModelBtn);
    expect(mockNavigate).toHaveBeenCalledWith({ to: '/admin/model-validation' });

    const openMatrixBtn = screen.getByRole('button', { name: /open matrix/i });
    fireEvent.click(openMatrixBtn);
    expect(mockNavigate).toHaveBeenCalledWith({ to: '/matrix' });
  });

  it('renders recent activity rows with score, status, and drilldown links', () => {
    vi.spyOn(useAdminSummaryModule, 'useAdminSummary').mockReturnValue({
      data: mockSummary,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<SystemSummaryResponse>);

    vi.spyOn(useAdminMatrixModule, 'useAdminMatrix').mockReturnValue({
      data: { items: mockMatrixRows, total: 2, page: 1, page_size: 5 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse>);

    render(<AdminHomePage />);

    expect(screen.getByText('IT101 Module 1')).toBeDefined();
    expect(screen.getByText('Faculty: Prof. Cruz')).toBeDefined();
    expect(screen.getByText('BSIT')).toBeDefined();
    expect(screen.getByText('COMPLETED')).toBeDefined();
    expect(screen.getByText('3.85')).toBeDefined();

    expect(screen.getByText('CS201 Algorithms')).toBeDefined();
    expect(screen.getByText('FAILED')).toBeDefined();
    expect(screen.getByText('2')).toBeDefined(); // Flag count
  });

  it('renders empty activity message when there are no records in the matrix', () => {
    vi.spyOn(useAdminSummaryModule, 'useAdminSummary').mockReturnValue({
      data: mockSummary,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<SystemSummaryResponse>);

    vi.spyOn(useAdminMatrixModule, 'useAdminMatrix').mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 5 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse>);

    render(<AdminHomePage />);

    expect(screen.getByText('No evaluation activity yet')).toBeDefined();
  });

  it('renders error message when matrix data fails to load', () => {
    vi.spyOn(useAdminSummaryModule, 'useAdminSummary').mockReturnValue({
      data: mockSummary,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<SystemSummaryResponse>);

    vi.spyOn(useAdminMatrixModule, 'useAdminMatrix').mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as UseQueryResult<MatrixListResponse>);

    render(<AdminHomePage />);

    expect(
      screen.getByText('Unable to load recent activity from the monitoring matrix.'),
    ).toBeDefined();
  });
});
