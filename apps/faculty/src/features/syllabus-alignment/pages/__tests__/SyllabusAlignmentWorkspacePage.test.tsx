// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SyllabusAlignmentWorkspacePage } from '../SyllabusAlignmentWorkspacePage';
import { documentsApi } from '@equiped/api-client';
import { alignmentApi } from '../../api/syllabusAlignment.api';

let mockRouteParams = { documentId: 'doc-1' };

vi.mock('@tanstack/react-router', () => ({
  useParams: () => mockRouteParams,
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

vi.mock('@equiped/api-client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@equiped/api-client')>();
  return {
    ...actual,
    documentsApi: {
      getDocument: vi.fn(),
    },
  };
});

vi.mock('../../api/syllabusAlignment.api', () => ({
  alignmentApi: {
    getAvailableSyllabi: vi.fn(),
    getCurrent: vi.fn(),
    start: vi.fn(),
  },
}));

describe('SyllabusAlignmentWorkspacePage Component', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    mockRouteParams = { documentId: 'doc-1' };

    vi.mocked(documentsApi.getDocument).mockResolvedValue({
      documentId: 'doc-1',
      title: 'Module 1 - Networking',
      chunks: [
        {
          chunkId: 'c-1',
          documentId: 'doc-1',
          text: 'Page 1 text',
          pageNumber: 1,
          chunkIndex: 0,
        },
        {
          chunkId: 'c-2',
          documentId: 'doc-1',
          text: 'Page 2 text',
          pageNumber: 2,
          chunkIndex: 1,
        },
      ],
      uploadedAt: '2026-08-01T00:00:00Z',
      processingStatus: 'PROCESSED',
      sourceType: 'slm',
      pageCount: 2,
      hasOcrPages: false,
    } as any);

    vi.mocked(alignmentApi.getAvailableSyllabi).mockResolvedValue({
      items: [
        {
          document_id: 'syl-1',
          title: 'Syllabus A',
          content_count: 5,
        },
        {
          document_id: 'syl-2',
          title: 'Syllabus B',
          content_count: 10,
        },
      ],
      total: 2,
    });

    vi.mocked(alignmentApi.getCurrent).mockResolvedValue(null);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function renderPage() {
    return render(
      <QueryClientProvider client={queryClient}>
        <SyllabusAlignmentWorkspacePage />
      </QueryClientProvider>,
    );
  }

  it('resets document-scoped state when documentId changes', async () => {
    const { rerender } = renderPage();

    expect(await screen.findByText('Module 1 - Networking')).toBeDefined();
    // Default is page 1 of 2
    expect(screen.getByText(/Page 1 of 2/i)).toBeDefined();

    // Now re-route to document 2
    mockRouteParams = { documentId: 'doc-2' };
    vi.mocked(documentsApi.getDocument).mockResolvedValue({
      documentId: 'doc-2',
      title: 'Module 2 - Database Systems',
      chunks: [
        {
          chunkId: 'c-3',
          documentId: 'doc-2',
          text: 'Page 1 DB',
          pageNumber: 1,
          chunkIndex: 0,
        },
      ],
      uploadedAt: '2026-08-01T00:00:00Z',
      processingStatus: 'PROCESSED',
      sourceType: 'slm',
      pageCount: 1,
      hasOcrPages: false,
    } as any);

    rerender(
      <QueryClientProvider client={queryClient}>
        <SyllabusAlignmentWorkspacePage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Module 2 - Database Systems')).toBeDefined();
    expect(screen.getByText(/Page 1 of 1/i)).toBeDefined();
  });
});
