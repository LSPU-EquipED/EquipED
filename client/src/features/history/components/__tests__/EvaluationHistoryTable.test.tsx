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

  function renderTable() {
    return render(
      <QueryClientProvider client={queryClient}>
        <EvaluationHistoryTable />
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

  it('renders history items with correct statuses and document titles', () => {
    const mockData: HistoryListResponse = {
      items: [
        {
          evaluation_id: 'eval-12345678-abcd',
          document_id: 'doc-1',
          document_title: 'Syllabus for Data Structures',
          syllabus_id: 'syl-1',
          curriculum_id: 'curr-1',
          status: 'COMPLETED',
          submitted_at: '2026-08-20T10:00:00Z',
          completed_at: '2026-08-20T10:05:00Z',
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
  });

  it('renders role badge and accessible scorecard action for targeted evaluations', () => {
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
          submitted_at: '2026-08-20T10:00:00Z',
          completed_at: '2026-08-20T10:05:00Z',
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
    expect(screen.getByRole('link', { name: /View audit scorecard for Operating Systems SLM/i })).toBeDefined();
  });

  it('triggers history query with selected target_agent when role filter is changed', () => {
    const useHistorySpy = vi.spyOn(useEvaluationHistoryModule, 'useEvaluationHistory').mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 10 },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<HistoryListResponse, Error>);

    renderTable();
    const roleTab = screen.getByRole('tab', { name: /Gender & Development/i });
    fireEvent.click(roleTab);
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

    const statusSelect = screen.getByLabelText(/Status:/i);
    fireEvent.change(statusSelect, { target: { value: 'FAILED' } });

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
});
