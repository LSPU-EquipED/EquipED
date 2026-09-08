// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MonitoringTable } from '../MonitoringTable';
import {
  formatProgressStatus,
  getCompletedDomainCount,
} from '../../utils';
import * as useMonitoringMatrixModule from '../../hooks/useMonitoringMatrix';
import type { MatrixListResponse } from '../../types';

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <span className={className}>{children}</span>,
}));

describe('domain progress helpers', () => {
  it('counts completed domains against the four target roles', () => {
    expect(getCompletedDomainCount(null)).toBe(0);
    expect(getCompletedDomainCount({})).toBe(0);
    expect(
      getCompletedDomainCount({
        sme: { subtotal: 3.5, max_score: 4, status: 'OK' },
        gad: { subtotal: 4, max_score: 4, status: 'OK' },
      }),
    ).toBe(2);
  });

  it('formats IN_PROGRESS status with domain completion counts', () => {
    expect(
      formatProgressStatus('IN_PROGRESS', {
        sme: { subtotal: 3.5, max_score: 4, status: 'OK' },
      }),
    ).toBe('IN PROGRESS (1/4 DOMAINS)');
    expect(formatProgressStatus('COMPLETED', null)).toBe('COMPLETED');
    expect(formatProgressStatus('SUBMITTED', null)).toBe('SUBMITTED');
  });
});

describe('MonitoringTable progressive domain badges', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('shows progressive status and per-domain score/pending badges', () => {
    const mockData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Algorithms Module',
          evaluation_status: 'IN_PROGRESS',
          synthesized_score: null,
          adjectival_rating: null,
          domain_scores: {
            sme: {
              version: 2,
              form_snapshot_id: 'snap-1',
              subtotal: 3.5,
              max_score: 4,
              status: 'OK',
            },
            gad: {
              version: 2,
              form_snapshot_id: 'snap-2',
              subtotal: 4,
              max_score: 4,
              status: 'OK',
            },
          },
          flag_count: 0,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };

    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useMonitoringMatrixModule.useMonitoringMatrix>);

    render(
      <QueryClientProvider client={queryClient}>
        <MonitoringTable />
      </QueryClientProvider>,
    );

    expect(screen.getByText('IN PROGRESS (2/4 DOMAINS)')).toBeDefined();
    expect(screen.getByText('SME 3.50')).toBeDefined();
    expect(screen.getByText('GAD 4')).toBeDefined();
    expect(screen.getByText('Coord Pending')).toBeDefined();
    expect(screen.getByText('ITSO Pending')).toBeDefined();
  });
});
