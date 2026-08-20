// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useDocumentDashboard } from '../useDocumentDashboard';
import { documentsFeatureApi } from '../../api/documents.api';
import type { ClientDocument, DocumentListResponse } from '@/shared/types/documents';

vi.mock('../../api/documents.api', () => ({
  documentsFeatureApi: {
    listDocuments: vi.fn(),
  },
}));

function createClientDocument(id: string, overrides: Partial<ClientDocument> = {}): ClientDocument {
  return {
    documentId: id,
    title: `Document ${id}`,
    courseTitle: 'IT 101',
    lessonTitle: 'Module 1',
    sourceType: 'slm',
    program: 'BSInfoTech',
    academicYear: '2025-2026',
    courseCode: 'IT101',
    pageCount: 10,
    processingStatus: 'PROCESSED',
    hasOcrPages: false,
    uploadedAt: '2026-08-15T10:00:00Z',
    chunks: [],
    ...overrides,
  };
}

function createQueryWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useDocumentDashboard', () => {
  beforeEach(() => {
    vi.mocked(documentsFeatureApi.listDocuments).mockReset();
  });

  it('handles >20 total documents, returns page 2 items when navigating to page 2', async () => {
    const page1Response: DocumentListResponse = {
      items: Array.from({ length: 10 }, (_, i) =>
        createClientDocument(`doc-${i + 1}`, { title: `Page 1 Doc ${i + 1}` }),
      ),
      total: 25,
      page: 1,
      pageSize: 10,
      stats: { total: 25, ready: 22, processing: 2, failed: 1 },
    };

    const page2Response: DocumentListResponse = {
      items: Array.from({ length: 10 }, (_, i) =>
        createClientDocument(`doc-${i + 11}`, { title: `Page 2 Doc ${i + 11}` }),
      ),
      total: 25,
      page: 2,
      pageSize: 10,
      stats: { total: 25, ready: 22, processing: 2, failed: 1 },
    };

    vi.mocked(documentsFeatureApi.listDocuments).mockImplementation(async (params) => {
      if (params?.page === 2) {
        return page2Response;
      }
      return page1Response;
    });

    const wrapper = createQueryWrapper();
    const { result } = renderHook(() => useDocumentDashboard(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(documentsFeatureApi.listDocuments).toHaveBeenCalledWith({
      sourceType: 'slm',
      page: 1,
      pageSize: 10,
      search: undefined,
      status: undefined,
    });
    expect(result.current.documents).toHaveLength(10);
    expect(result.current.documents[0].title).toBe('Page 1 Doc 1');
    expect(result.current.totalPages).toBe(3);
    expect(result.current.stats).toEqual({ total: 25, ready: 22, processing: 2, failed: 1 });

    act(() => {
      result.current.setPage(2);
    });

    expect(result.current.page).toBe(2);

    await waitFor(() => {
      expect(result.current.documents[0]?.title).toBe('Page 2 Doc 11');
    });

    expect(documentsFeatureApi.listDocuments).toHaveBeenCalledWith({
      sourceType: 'slm',
      page: 2,
      pageSize: 10,
      search: undefined,
      status: undefined,
    });
    expect(result.current.documents).toHaveLength(10);
  });

  it('propagates search queries to the API and resets page to 1', async () => {
    const defaultResponse: DocumentListResponse = {
      items: [createClientDocument('doc-1', { title: 'General IT' })],
      total: 25,
      page: 1,
      pageSize: 10,
      stats: { total: 25, ready: 25, processing: 0, failed: 0 },
    };

    const searchResponse: DocumentListResponse = {
      items: [createClientDocument('doc-2', { title: 'Data Structures' })],
      total: 1,
      page: 1,
      pageSize: 10,
      stats: { total: 1, ready: 1, processing: 0, failed: 0 },
    };

    vi.mocked(documentsFeatureApi.listDocuments).mockImplementation(async (params) => {
      if (params?.search === 'Structures') {
        return searchResponse;
      }
      return defaultResponse;
    });

    const wrapper = createQueryWrapper();
    const { result } = renderHook(() => useDocumentDashboard(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.setPage(2);
    });
    expect(result.current.page).toBe(2);

    act(() => {
      result.current.setSearch('  Structures  ');
    });

    expect(result.current.page).toBe(1);
    expect(result.current.search).toBe('  Structures  ');

    await waitFor(() => {
      expect(result.current.documents[0]?.title).toBe('Data Structures');
    });

    expect(documentsFeatureApi.listDocuments).toHaveBeenCalledWith({
      sourceType: 'slm',
      page: 1,
      pageSize: 10,
      search: 'Structures',
      status: undefined,
    });
  });

  it('propagates status filter (PROCESSED, PROCESSING, FAILED) to API and resets page to 1', async () => {
    const mockResponse: DocumentListResponse = {
      items: [createClientDocument('doc-1', { processingStatus: 'PROCESSED' })],
      total: 1,
      page: 1,
      pageSize: 10,
      stats: { total: 10, ready: 5, processing: 3, failed: 2 },
    };

    vi.mocked(documentsFeatureApi.listDocuments).mockResolvedValue(mockResponse);

    const wrapper = createQueryWrapper();
    const { result } = renderHook(() => useDocumentDashboard(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // PROCESSED -> ready
    act(() => {
      result.current.setPage(3);
    });
    act(() => {
      result.current.setStatusFilter('PROCESSED');
    });
    expect(result.current.page).toBe(1);
    await waitFor(() => {
      expect(documentsFeatureApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'ready', page: 1 }),
      );
    });

    // PROCESSING -> processing
    act(() => {
      result.current.setStatusFilter('PROCESSING');
    });
    await waitFor(() => {
      expect(documentsFeatureApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'processing', page: 1 }),
      );
    });

    // FAILED -> failed
    act(() => {
      result.current.setStatusFilter('FAILED');
    });
    await waitFor(() => {
      expect(documentsFeatureApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'failed', page: 1 }),
      );
    });

    // all -> undefined
    act(() => {
      result.current.setStatusFilter('all');
    });
    await waitFor(() => {
      expect(documentsFeatureApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ status: undefined, page: 1 }),
      );
    });
  });

  it('resets page when pageSize changes', async () => {
    const mockResponse: DocumentListResponse = {
      items: [createClientDocument('doc-1')],
      total: 50,
      page: 1,
      pageSize: 25,
      stats: { total: 50, ready: 50, processing: 0, failed: 0 },
    };

    vi.mocked(documentsFeatureApi.listDocuments).mockResolvedValue(mockResponse);

    const wrapper = createQueryWrapper();
    const { result } = renderHook(() => useDocumentDashboard(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.setPage(3);
    });
    expect(result.current.page).toBe(3);

    act(() => {
      result.current.setPageSize(25);
    });
    expect(result.current.page).toBe(1);
    expect(result.current.pageSize).toBe(25);

    await waitFor(() => {
      expect(documentsFeatureApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ pageSize: 25, page: 1 }),
      );
    });
  });

  it('polls whenever stats.processing > 0 even if the current page items contain 0 processing documents', async () => {
    // Current page has 0 processing items, but stats.processing is 3 (off page)
    const responseWithOffPageProcessing: DocumentListResponse = {
      items: [
        createClientDocument('doc-1', { processingStatus: 'PROCESSED' }),
        createClientDocument('doc-2', { processingStatus: 'PROCESSED' }),
      ],
      total: 30,
      page: 1,
      pageSize: 10,
      stats: { total: 30, ready: 27, processing: 3, failed: 0 },
    };

    vi.mocked(documentsFeatureApi.listDocuments).mockResolvedValue(responseWithOffPageProcessing);

    const wrapper = createQueryWrapper();
    const { result } = renderHook(() => useDocumentDashboard(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.stats.processing).toBe(3);
    expect(result.current.documents.every((d) => d.processingStatus === 'PROCESSED')).toBe(true);
  });
});
