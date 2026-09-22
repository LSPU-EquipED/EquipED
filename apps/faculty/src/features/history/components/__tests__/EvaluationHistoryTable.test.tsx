// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { QueryClient, QueryClientProvider, type UseQueryResult } from '@tanstack/react-query';
import { EvaluationHistoryTable } from '../EvaluationHistoryTable';
import * as useEvaluationHistoryModule from '../../hooks/useEvaluationHistory';
import type { HistoryListResponse } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    to,
    params,
    children,
    ...props
  }: {
    to?: string;
    params?: Record<string, string>;
    children?: ReactNode;
  } & ComponentPropsWithoutRef<'a'>) => {
    let href = to || props.href || '#';
    if (params && to) {
      Object.entries(params).forEach(([key, val]) => {
        href = href.replace(`$${key}`, val);
      });
    }
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  },
  Outlet: () => null,
}));

describe('EvaluationHistoryTable Component', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function renderTable(props?: Parameters<typeof EvaluationHistoryTable>[0]) {
    return render(
      <QueryClientProvider client={queryClient}>
        <EvaluationHistoryTable {...props} />
      </QueryClientProvider>,
    );
  }

  it('renders loading state when fetching records', () => {
    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();
    expect(screen.getByRole('status', { name: 'Loading evaluation history' })).toBeDefined();
  });

  it('renders empty state when no records exist', () => {
    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();
    expect(screen.getByText('No evaluations yet')).toBeDefined();
  });

  it('renders error state on query failure', () => {
    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();
    expect(screen.getByText('Failed to load evaluation history.')).toBeDefined();
  });

  it('renders history items with correct statuses, document titles, and scorecard link for all-agent runs', () => {
    const mockData: HistoryListResponse = {
      items: [
        {
          evaluation_id: 'eval-12345678-abcd',
          document_id: 'doc-1',
          document_title: 'Syllabus for Data Structures',
          syllabus_id: 'syl-1',
          curriculum_id: 'curr-1',
          status: 'COMPLETED',
          target_agent: 'all',
          error_message: null,
          confirmed_program: 'BSCS',
          submitted_at: '2026-08-20T10:00:00Z',
          completed_at: '2026-08-20T10:05:00Z',
          duration_seconds: 300,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };

    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();

    expect(screen.getByText('Syllabus for Data Structures')).toBeDefined();
    expect(screen.getByText('COMPLETED')).toBeDefined();
    expect(screen.getByText('1 evaluation found')).toBeDefined();
    const scorecardLink = screen.getByRole('link', { name: /View audit scorecard for Syllabus for Data Structures/i });
    expect(scorecardLink).toBeDefined();
    expect(scorecardLink.getAttribute('href')).toBe('/evaluations/eval-12345678-abcd');
    expect(scorecardLink.textContent).toBe('Scorecard');
  });

  it('renders role badge and links directly to specialist desk for single-agent runs', () => {
    const mockData: HistoryListResponse = {
      items: [
        {
          evaluation_id: 'eval-targeted-1234',
          document_id: 'doc-1',
          document_title: 'Operating Systems SLM',
          syllabus_id: 'syl-1',
          curriculum_id: 'curr-1',
          status: 'COMPLETED',
          target_agent: 'sme',
          error_message: null,
          confirmed_program: 'BSCS',
          submitted_at: '2026-08-20T10:00:00Z',
          completed_at: '2026-08-20T10:05:00Z',
          duration_seconds: 300,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };

    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();

    expect(screen.getByText('SME')).toBeDefined();
    expect(screen.queryByRole('link', { name: /workspace/i })).toBeNull();
    const actionLink = screen.getByRole('link', { name: /View audit scorecard for Operating Systems SLM/i });
    expect(actionLink).toBeDefined();
    expect(actionLink.getAttribute('href')).toBe('/evaluations/eval-targeted-1234');
    expect(actionLink.textContent).toBe('Scorecard');
  });
  it('renders scorecard link with text Scorecard when target_agent is explicitly all', () => {
    const mockData: HistoryListResponse = {
      items: [
        {
          evaluation_id: 'eval-all-5678',
          document_id: 'doc-2',
          document_title: 'Full Curriculum Bundle',
          syllabus_id: 'syl-2',
          curriculum_id: 'curr-2',
          status: 'COMPLETED',
          target_agent: 'all',
          error_message: null,
          confirmed_program: 'BSCS',
          submitted_at: '2026-08-20T10:00:00Z',
          completed_at: '2026-08-20T10:05:00Z',
          duration_seconds: 300,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };

    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();

    expect(screen.getByText('All Domains')).toBeDefined();
    const scorecardLink = screen.getByRole('link', { name: /View audit scorecard for Full Curriculum Bundle/i });
    expect(scorecardLink).toBeDefined();
    expect(scorecardLink.getAttribute('href')).toBe('/evaluations/eval-all-5678');
    expect(scorecardLink.textContent).toBe('Scorecard');
  });

  it('triggers history query with selected target_agent when role filter is changed', () => {
    const useHistorySpy = vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 10 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();
    const roleSelect = screen.getByRole('button', { name: 'Role' });
    fireEvent.click(roleSelect);
    fireEvent.click(screen.getByRole('option', { name: 'Gender & Development' }));
    expect(useHistorySpy).toHaveBeenCalledWith(
      expect.objectContaining({
        target_agent: 'gad',
      }),
    );
  });

  it('triggers history query with selected status when status filter is changed', () => {
    const useHistorySpy = vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 10 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();

    const statusSelect = screen.getByRole('button', { name: 'Status' });
    fireEvent.click(statusSelect);
    fireEvent.click(screen.getByRole('option', { name: 'Failed' }));

    expect(useHistorySpy).toHaveBeenCalledWith(
      expect.objectContaining({
        status: 'FAILED',
      }),
    );
  });
  it('history feature never imports from other features (strict feature boundary)', () => {
    const historyDir = path.resolve(__dirname, '../..');
    expect(path.basename(historyDir)).toBe('history');

    const files: string[] = [];
    function scanDir(dir: string) {
      for (const entry of fs.readdirSync(dir)) {
        const full = path.join(dir, entry);
        if (fs.statSync(full).isDirectory()) {
          if (entry !== '__tests__') scanDir(full);
        } else if (/\.(ts|tsx)$/.test(entry)) {
          files.push(full);
        }
      }
    }
    scanDir(historyDir);

    expect(files.length).toBeGreaterThan(0);
    const crossFeaturePattern = /from\s+['"].*features\/(?!history)[^/]+.*['"]/;
    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      expect(
        crossFeaturePattern.test(content),
        `Found cross-feature import in ${file}`,
      ).toBe(false);
    }
  });

  it('hides role filter dropdown when user only has a single permitted desk and defaults query to it', () => {
    const useHistorySpy = vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 10 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable({ evaluatorPermissions: ['coordinator'] });

    // Single-desk users don't see a redundant role dropdown
    expect(screen.queryByRole('button', { name: 'Role' })).toBeNull();

    // Query was triggered for coordinator
    expect(useHistorySpy).toHaveBeenCalledWith(
      expect.objectContaining({
        target_agent: 'coordinator',
      }),
    );
  });

  it('shows all role options when faculty has empty permissions (unrestricted default)', () => {
    renderTable({ evaluatorPermissions: [], userRole: 'faculty' });

    const roleSelect = screen.getByRole('button', { name: 'Role' });
    expect(roleSelect).toBeDefined();
    fireEvent.click(roleSelect);
    expect(screen.getByRole('option', { name: 'Subject Matter Expert' })).toBeDefined();
    expect(screen.getByRole('option', { name: 'Program Coordinator' })).toBeDefined();
    expect(screen.getByRole('option', { name: 'Gender & Development' })).toBeDefined();
    expect(screen.getByRole('option', { name: 'Innovation and Technology Support Office' })).toBeDefined();
  });
  it('shows all role options for admin user even if permissions are empty', () => {
    renderTable({ evaluatorPermissions: [], userRole: 'admin' });

    const roleSelect = screen.getByRole('button', { name: 'Role' });
    expect(roleSelect).toBeDefined();
    fireEvent.click(roleSelect);
    expect(screen.getByRole('option', { name: 'Subject Matter Expert' })).toBeDefined();
    expect(screen.getByRole('option', { name: 'Program Coordinator' })).toBeDefined();
    expect(screen.getByRole('option', { name: 'Gender & Development' })).toBeDefined();
    expect(screen.getByRole('option', { name: 'Innovation and Technology Support Office' })).toBeDefined();
  });

  it('renders metric cards from server stats when present', () => {
    const mockDataWithStats: HistoryListResponse = {
      items: [
        {
          evaluation_id: 'eval-1',
          document_id: 'doc-1',
          document_title: 'Doc 1',
          syllabus_id: 'syl-1',
          curriculum_id: 'curr-1',
          status: 'COMPLETED',
          target_agent: 'sme',
          error_message: null,
          confirmed_program: 'BSCS',
          submitted_at: '2026-08-20T10:00:00Z',
          completed_at: '2026-08-20T10:05:00Z',
          duration_seconds: 300,
        },
      ],
      total: 100,
      page: 1,
      page_size: 1,
      stats: {
        total: 100,
        completed: 85,
        in_progress: 12,
        average_duration_seconds: 125,
      },
    };

    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: mockDataWithStats,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();

    // Stats values: total 100, completed 85, in_progress 12, avg duration 2m 5s
    expect(screen.getByText('100')).toBeDefined();
    expect(screen.getByText('85')).toBeDefined();
    expect(screen.getByText('12')).toBeDefined();
    expect(screen.getByText('2m 5s')).toBeDefined();
  });

  it('renders stats.total when stats.total differs from response total, and treats average_duration_seconds=0 as 0s', () => {
    const mockDataWithZeroDuration: HistoryListResponse = {
      items: [],
      total: 50, // e.g. filtered count
      page: 1,
      page_size: 10,
      stats: {
        total: 200, // server-scoped aggregate
        completed: 150,
        in_progress: 25,
        average_duration_seconds: 0,
      },
    };

    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: mockDataWithZeroDuration,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();

    expect(screen.getByText('200')).toBeDefined();
    expect(screen.getByText('150')).toBeDefined();
    expect(screen.getByText('25')).toBeDefined();
    expect(screen.getByText('0s')).toBeDefined();
  });

  it('falls back to page-derived values when server stats are absent', () => {
    const mockDataWithoutStats: HistoryListResponse = {
      items: [
        {
          evaluation_id: 'eval-1',
          document_id: 'doc-1',
          document_title: 'Doc 1',
          syllabus_id: 'syl-1',
          curriculum_id: 'curr-1',
          status: 'COMPLETED',
          target_agent: 'sme',
          error_message: null,
          confirmed_program: 'BSCS',
          submitted_at: '2026-08-20T10:00:00Z',
          completed_at: '2026-08-20T10:02:00Z',
          duration_seconds: 120,
        },
        {
          evaluation_id: 'eval-2',
          document_id: 'doc-2',
          document_title: 'Doc 2',
          syllabus_id: 'syl-2',
          curriculum_id: 'curr-2',
          status: 'EVALUATING',
          target_agent: 'sme',
          error_message: null,
          confirmed_program: 'BSCS',
          submitted_at: '2026-08-20T10:10:00Z',
          completed_at: null,
          duration_seconds: null,
        },
      ],
      total: 2,
      page: 1,
      page_size: 10,
    };

    vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: mockDataWithoutStats,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();

    // Fallback: total 2, completed 1, in_progress 1, avg duration 2m 0s
    expect(screen.getByText('2')).toBeDefined();
    expect(screen.getAllByText('1')).toHaveLength(2); // One for completed, one for in_progress
    expect(screen.getAllByText('2m 0s').length).toBeGreaterThanOrEqual(1);
  });
});
