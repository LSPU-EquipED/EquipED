// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SyllabusAlignmentPage } from '../SyllabusAlignmentPage';
import { alignmentApi } from '../../api/syllabusAlignment.api';
import type { AlignmentSlmListResponse } from '../../types';

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
}));

describe('SyllabusAlignmentPage Component', () => {
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

  function renderPage() {
    return render(
      <QueryClientProvider client={queryClient}>
        <SyllabusAlignmentPage />
      </QueryClientProvider>,
    );
  }

  it('renders metric cards using response.stats when present', async () => {
    const mockResponse: AlignmentSlmListResponse = {
      items: [
        {
          document_id: 'slm-1',
          title: 'Networking 101',
          course_title: 'Intro to Networking',
          lesson_title: 'Module 1',
          program: 'BSCS',
          course_code: 'CS101',
          processing_status: 'PROCESSED',
          uploaded_at: '2026-08-01T00:00:00Z',
          evaluation_available: true,
          current_result: {
            alignment_id: 'align-1',
            slm_document_id: 'slm-1',
            syllabus_document_id: 'syl-1',
            requested_by: 'user-1',
            status: 'COMPLETED',
            alignment_level: 'MEETS',
            advisory_only: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:01:00Z',
          },
        },
      ],
      total: 50,
      page: 1,
      page_size: 10,
      stats: {
        total: 50,
        meets: 25,
        partially_meets: 15,
        needs_attention: 6,
        pending: 4,
      },
    };

    vi.spyOn(alignmentApi, 'listSlms').mockResolvedValue(mockResponse);

    renderPage();

    expect(await screen.findByText('50')).toBeDefined();
    expect(screen.getByText('25')).toBeDefined();
    expect(screen.getByText('15')).toBeDefined();
    expect(screen.getByText('6')).toBeDefined();
    expect(screen.getByText('+ 4 pending')).toBeDefined();
  });

  it('falls back to calculating metrics from items when stats is not returned', async () => {
    const mockResponse: AlignmentSlmListResponse = {
      items: [
        {
          document_id: 'slm-1',
          title: 'Module 1',
          processing_status: 'PROCESSED',
          uploaded_at: '2026-08-01T00:00:00Z',
          evaluation_available: true,
          current_result: {
            alignment_id: 'align-1',
            slm_document_id: 'slm-1',
            syllabus_document_id: 'syl-1',
            requested_by: 'user-1',
            status: 'COMPLETED',
            alignment_level: 'MEETS',
            advisory_only: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:01:00Z',
          },
        },
        {
          document_id: 'slm-2',
          title: 'Module 2',
          processing_status: 'PROCESSED',
          uploaded_at: '2026-08-01T00:00:00Z',
          evaluation_available: true,
          current_result: {
            alignment_id: 'align-2',
            slm_document_id: 'slm-2',
            syllabus_document_id: 'syl-2',
            requested_by: 'user-1',
            status: 'COMPLETED',
            alignment_level: 'PARTIALLY_MEETS',
            advisory_only: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:01:00Z',
          },
        },
        {
          document_id: 'slm-3',
          title: 'Module 3',
          processing_status: 'PROCESSED',
          uploaded_at: '2026-08-01T00:00:00Z',
          evaluation_available: true,
          current_result: {
            alignment_id: 'align-3',
            slm_document_id: 'slm-3',
            syllabus_document_id: 'syl-3',
            requested_by: 'user-1',
            status: 'COMPLETED',
            alignment_level: 'DOES_NOT_MEET',
            advisory_only: true,
            created_at: '2026-08-01T00:00:00Z',
            updated_at: '2026-08-01T00:01:00Z',
          },
        },
      ],
      total: 3,
      page: 1,
      page_size: 10,
    };

    vi.spyOn(alignmentApi, 'listSlms').mockResolvedValue(mockResponse);

    renderPage();

    expect(await screen.findByText('3')).toBeDefined();
    // 1 meets, 1 partially meets, 1 attention, 0 pending -> 'divergent'
    expect(screen.getAllByText('1')).toHaveLength(3);
    expect(screen.getByText('divergent')).toBeDefined();
  });
});
