// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { QueryClient, QueryClientProvider, type UseQueryResult } from '@tanstack/react-query';
import { EvaluationHistoryTable } from '../EvaluationHistoryTable';
import * as useEvaluationHistoryModule from '../../hooks/useEvaluationHistory';
import type { HistoryListResponse } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, ...props }: ComponentPropsWithoutRef<'a'> & { children?: ReactNode }) => (
    <a {...props}>{children}</a>
  ),
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
    expect(screen.getByText('Loading evaluation history…')).toBeDefined();
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
