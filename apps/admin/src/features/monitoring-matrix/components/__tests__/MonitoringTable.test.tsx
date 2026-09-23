// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider, type UseQueryResult } from '@tanstack/react-query';
import { MonitoringTable } from '../MonitoringTable';
import * as useMonitoringMatrixModule from '../../hooks/useMonitoringMatrix';
import type { MatrixListResponse } from '../../types';

const mockNavigate = vi.fn();

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    to,
    params,
    children,
    className,
    onClick,
    ...rest
  }: {
    to: string;
    params?: Record<string, string>;
    children?: React.ReactNode;
    className?: string;
    onClick?: (e: React.MouseEvent) => void;
    [key: string]: unknown;
  }) => {
    let href = to;
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        href = href.replace(`$${key}`, val);
      });
    }
    return (
      <a href={href} className={className} onClick={onClick} {...rest}>
        {children}
      </a>
    );
  },
  useNavigate: () => mockNavigate,
}));

describe('MonitoringTable Component', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  function renderTable() {
    return render(
      <QueryClientProvider client={queryClient}>
        <MonitoringTable />
      </QueryClientProvider>,
    );
  }

  it('renders Form Revision column and displays revision context supplied by API', () => {
    const mockData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Algorithms Module',
          evaluation_status: 'COMPLETED',
          synthesized_score: 92,
          adjectival_rating: 'Very Satisfactory',
          domain_scores: {
            sme: {
              version: 2,
              form_snapshot_id: 'snap-1',
              subtotal: 4,
              max_score: 4,
              status: 'OK',
            },
          },
          flag_count: 0,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
        {
          matrix_id: 'mat-2',
          document_id: 'doc-2',
          evaluation_id: 'eval-2',
          faculty_name: 'Prof. Reyes',
          program: 'BSInfoTech',
          document_title: 'Web Dev Module',
          evaluation_status: 'COMPLETED',
          synthesized_score: 85,
          adjectival_rating: 'Satisfactory',
          domain_scores: {
            sme: {
              subtotal: 3,
              max_score: 4,
              status: 'OK',
            },
          },
          flag_count: 1,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-21T10:00:00Z',
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
      metrics: {
        completed_count: 2,
        passing_count: 2,
        flagged_count: 1,
        total_flags: 1,
        quality_pass_rate: 100.0,
      },
    };

    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useMonitoringMatrixModule.useMonitoringMatrix>);

    renderTable();

    // Check collapsible metadata contains Form Revision
    expect(screen.getAllByText(/Form Revision/i).length).toBeGreaterThan(0);

    // Check row 1 has revision
    expect(screen.getByText('Rev 2')).toBeDefined();

    // Check row 2 has exact legacy notice
    expect(screen.getByText('Legacy — form snapshot unavailable')).toBeDefined();
  });

  it('renders operational KPI metrics and row details correctly', () => {
    const mockData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-101',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Data Structures Module',
          evaluation_status: 'COMPLETED',
          synthesized_score: 3.85,
          adjectival_rating: 'Very Satisfactory',
          domain_scores: {
            sme: {
              version: 2,
              form_snapshot_id: 'snap-sme',
              subtotal: 4.0,
              max_score: 4,
              status: 'OK',
              adjectival_rating: 'Very Satisfactory',
              summary: 'Rigorous subject matter depth and clear exercises.',
            },
            coordinator: {
              version: 1,
              form_snapshot_id: 'snap-coord',
              subtotal: 3.7,
              max_score: 4,
              status: 'OK',
              adjectival_rating: 'Satisfactory',
              summary: 'Aligned with BSCS course syllabus.',
            },
          },
          flag_count: 2,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-22T10:00:00Z',
        },
      ],
      total: 50,
      page: 1,
      page_size: 20,
      metrics: {
        completed_count: 40,
        passing_count: 36,
        flagged_count: 8,
        total_flags: 14,
        quality_pass_rate: 90.0,
      },
    };

    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useMonitoringMatrixModule.useMonitoringMatrix>);

    renderTable();

    // KPI strip check
    expect(screen.getByText('Evaluated Modules')).toBeDefined();
    expect(screen.getByText('Quality Pass Rate')).toBeDefined();
    expect(screen.queryByText('Accredited Quality Rate')).toBeNull();
    expect(screen.getByText('Flagged for Audit')).toBeDefined();
    expect(screen.getByText('Total Issue Flags')).toBeDefined();

    // Metric values check: Evaluated Modules uses completed_count (40), not total (50)
    expect(screen.getByText('40')).toBeDefined();
    expect(screen.getAllByText('50').length).toBeGreaterThanOrEqual(1); // total repository records in pagination
    expect(screen.getByText('90.0%')).toBeDefined();
    expect(screen.getByText('8')).toBeDefined();
    expect(screen.getByText('14')).toBeDefined();

    // Row metadata
    expect(screen.getByText('Data Structures Module')).toBeDefined();
    expect(screen.getByText('Faculty: Dr. Santos')).toBeDefined();
    expect(screen.getByText('BSCS')).toBeDefined();
    expect(screen.getByText('Rev 1, 2')).toBeDefined();
    expect(screen.getByText('Very Satisfactory')).toBeDefined();
  });

  it('renders COMPLETED_PARTIAL evaluation status with warning variant badge in matrix table row', () => {
    const partialData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-part-1',
          document_id: 'doc-part-1',
          evaluation_id: 'eval-part-1',
          faculty_name: 'Engr. Cruz',
          program: 'BSIT',
          document_title: 'Cloud Computing Module',
          evaluation_status: 'COMPLETED_PARTIAL',
          synthesized_score: 3.2,
          adjectival_rating: 'Satisfactory',
          domain_scores: null,
          flag_count: 0,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-25T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      metrics: {
        completed_count: 1,
        passing_count: 1,
        flagged_count: 0,
        total_flags: 0,
        quality_pass_rate: 100.0,
      },
    };

    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: partialData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useMonitoringMatrixModule.useMonitoringMatrix>);

    renderTable();

    const badge = screen.getByText('COMPLETED PARTIAL');
    expect(badge).toBeDefined();
    expect(badge.className).toContain('bg-warning-soft');
    expect(badge.className).toContain('text-warning');
  });

  it('renders clean empty state when data has zero items', () => {
    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        metrics: {
          completed_count: 0,
          passing_count: 0,
          flagged_count: 0,
          total_flags: 0,
          quality_pass_rate: null,
        },
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useMonitoringMatrixModule.useMonitoringMatrix>);

    renderTable();

    expect(screen.getByText('No evaluation records yet')).toBeDefined();
  });

  it('renders pagination controls and navigates pages', () => {
    const mockData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Module 1',
          evaluation_status: 'COMPLETED',
          synthesized_score: 3.9,
          adjectival_rating: 'Very Satisfactory',
          domain_scores: null,
          flag_count: 0,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
      ],
      total: 45,
      page: 1,
      page_size: 10,
      metrics: {
        completed_count: 35,
        passing_count: 30,
        flagged_count: 4,
        total_flags: 6,
        quality_pass_rate: 85.7,
      },
    };

    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse, Error>);

    renderTable();

    expect(screen.getByText(/Showing/)).toBeDefined();
    expect(screen.getByText('1–10')).toBeDefined();
    expect(screen.getAllByText('45').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDefined();
  });

  it('passes trimmed search query to useMonitoringMatrix hook and resets page on change', () => {
    const useMonitoringMatrixSpy = vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
        metrics: {
          completed_count: 0,
          passing_count: 0,
          flagged_count: 0,
          total_flags: 0,
          quality_pass_rate: null,
        },
      },
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse, Error>);

    renderTable();

    expect(useMonitoringMatrixSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        search: undefined,
        page: 1,
      }),
    );

    const searchInput = screen.getByLabelText('Search monitoring matrix');
    fireEvent.change(searchInput, { target: { value: '   Data Structures   ' } });

    expect(useMonitoringMatrixSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        search: 'Data Structures',
        page: 1,
      }),
    );
  });

  it('renders server items and total count directly without locally filtering page', () => {
    const mockData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Unrelated Title Returned By Server Search',
          evaluation_status: 'COMPLETED',
          synthesized_score: 92,
          adjectival_rating: 'Very Satisfactory',
          domain_scores: null,
          flag_count: 0,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
      ],
      total: 55, // server reports total 55 matches across all pages
      page: 1,
      page_size: 10,
      metrics: {
        completed_count: 40,
        passing_count: 38,
        flagged_count: 2,
        total_flags: 3,
        quality_pass_rate: 95.0,
      },
    };

    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse, Error>);

    renderTable();

    // Type a search string that does NOT match "Unrelated Title Returned By Server Search" locally
    const searchInput = screen.getByLabelText('Search monitoring matrix');
    fireEvent.change(searchInput, { target: { value: 'quantum physics' } });

    // Item returned from server must still be rendered because filtering is server-side
    expect(screen.getByText('Unrelated Title Returned By Server Search')).toBeDefined();
    // Total records reflects server's total count, not 1 or 0
    expect(screen.getAllByText('55').length).toBeGreaterThanOrEqual(1);
  });

  it('displays em dash when quality_pass_rate is null and metrics remain constant across page size changes', () => {
    const mockMetrics = {
      completed_count: 0,
      passing_count: 0,
      flagged_count: 3,
      total_flags: 7,
      quality_pass_rate: null,
    };

    const page1Data: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Module 1',
          evaluation_status: 'IN_PROGRESS',
          synthesized_score: null,
          adjectival_rating: null,
          domain_scores: null,
          flag_count: 1,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
      ],
      total: 50,
      page: 1,
      page_size: 10,
      metrics: mockMetrics,
    };

    const useMonitoringSpy = vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: page1Data,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse, Error>);

    const { rerender } = renderTable();

    // Verify pass rate is truthful '—' when null
    const passRateHeader = screen.getByText('Quality Pass Rate');
    const passRateCard = passRateHeader.closest('div');
    expect(passRateCard?.textContent).toContain('—');

    // Total flags and flagged count reflect server metrics, not page items (which only has 1 flag)
    expect(screen.getByText('3')).toBeDefined();
    expect(screen.getByText('7')).toBeDefined();
    expect(screen.getAllByText('50').length).toBeGreaterThanOrEqual(1);

    // Rerender simulating different page size response (e.g. page_size: 25, 2 items on page)
    const page2Data: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Module 1',
          evaluation_status: 'IN_PROGRESS',
          synthesized_score: null,
          adjectival_rating: null,
          domain_scores: null,
          flag_count: 1,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
        {
          matrix_id: 'mat-2',
          document_id: 'doc-2',
          evaluation_id: 'eval-2',
          faculty_name: 'Prof. Cruz',
          program: 'BSCS',
          document_title: 'Module 2',
          evaluation_status: 'IN_PROGRESS',
          synthesized_score: null,
          adjectival_rating: null,
          domain_scores: null,
          flag_count: 2,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T11:00:00Z',
        },
      ],
      total: 50,
      page: 1,
      page_size: 25,
      metrics: mockMetrics,
    };

    useMonitoringSpy.mockReturnValue({
      data: page2Data,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse, Error>);

    rerender(
      <QueryClientProvider client={queryClient}>
        <MonitoringTable />
      </QueryClientProvider>,
    );

    // Ribbon values remain identical across page size changes
    expect(passRateCard?.textContent).toContain('—');
    expect(screen.getByText('3')).toBeDefined();
    expect(screen.getByText('7')).toBeDefined();
    expect(screen.getAllByText('50').length).toBeGreaterThanOrEqual(1);
  });

  it('displays exact completed_count metric (including 0) and falls back to em dash when metrics missing', () => {
    const zeroMetricsData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-sub-1',
          document_id: 'doc-sub-1',
          evaluation_id: 'eval-sub-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Submitted SLM',
          evaluation_status: 'SUBMITTED',
          synthesized_score: null,
          adjectival_rating: null,
          domain_scores: null,
          flag_count: 0,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
      ],
      total: 10,
      page: 1,
      page_size: 10,
      metrics: {
        completed_count: 0,
        passing_count: 0,
        flagged_count: 0,
        total_flags: 0,
        quality_pass_rate: null,
      },
    };

    const useMonitoringSpy = vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: zeroMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse, Error>);

    const { rerender } = renderTable();

    // Evaluated Modules KPI must display '0', NOT '10' (total records)
    const evaluatedHeader = screen.getByText('Evaluated Modules');
    const evaluatedCard = evaluatedHeader.closest('div');
    expect(evaluatedCard?.textContent).toContain('0');
    expect(evaluatedCard?.textContent).not.toContain('10');

    // When metrics is undefined, display '—', NOT zero or total
    const missingMetricsData: MatrixListResponse = {
      items: zeroMetricsData.items,
      total: 10,
      page: 1,
      page_size: 10,
      metrics: undefined as unknown as MatrixListResponse['metrics'],
    };

    useMonitoringSpy.mockReturnValue({
      data: missingMetricsData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse, Error>);

    rerender(
      <QueryClientProvider client={queryClient}>
        <MonitoringTable />
      </QueryClientProvider>,
    );

    const reEvaluatedCard = screen.getByText('Evaluated Modules').closest('div');
    expect(reEvaluatedCard?.textContent).toContain('—');
  });

  it('collapses expanded rows when search changes, program changes, or page changes', () => {
    const mockData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Expandable Module 1',
          evaluation_status: 'COMPLETED',
          synthesized_score: 95,
          adjectival_rating: 'Very Satisfactory',
          domain_scores: null,
          flag_count: 0,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
      ],
      total: 50,
      page: 1,
      page_size: 10,
      metrics: {
        completed_count: 10,
        passing_count: 9,
        flagged_count: 1,
        total_flags: 1,
        quality_pass_rate: 90.0,
      },
    };

    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MatrixListResponse, Error>);

    renderTable();

    const disclosureBtn = screen.getByLabelText(/Expand details for Expandable Module 1/i);
    expect(disclosureBtn.getAttribute('aria-expanded')).toBe('false');

    // Expand the row
    fireEvent.click(disclosureBtn);
    expect(disclosureBtn.getAttribute('aria-expanded')).toBe('true');

    // Changing search collapses expanded row
    const searchInput = screen.getByLabelText('Search monitoring matrix');
    fireEvent.change(searchInput, { target: { value: 'New Search' } });
    expect(disclosureBtn.getAttribute('aria-expanded')).toBe('false');

    // Re-expand
    fireEvent.click(disclosureBtn);
    expect(disclosureBtn.getAttribute('aria-expanded')).toBe('true');

    // Changing program collapses expanded row
    const programTrigger = screen.getByRole('button', { name: 'Filter by program' });
    fireEvent.click(programTrigger);
    const cSOption = screen.getByRole('option', { name: /Computer Science/i });
    fireEvent.click(cSOption);
    expect(disclosureBtn.getAttribute('aria-expanded')).toBe('false');

    // Re-expand
    fireEvent.click(disclosureBtn);
    expect(disclosureBtn.getAttribute('aria-expanded')).toBe('true');

    // Changing page (e.g. Next button) collapses expanded row
    const nextBtn = screen.getByRole('button', { name: /Next/i });
    fireEvent.click(nextBtn);
    expect(disclosureBtn.getAttribute('aria-expanded')).toBe('false');
  });
});
