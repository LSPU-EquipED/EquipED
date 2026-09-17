// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSlmStorage } from '../useSlmStorage';
import { documentsApi } from '@equiped/api-client';
import type { ClientDocument, DocumentListResponse } from '@equiped/types';

vi.mock('@equiped/api-client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@equiped/api-client')>();
  return {
    ...actual,
    documentsApi: {
      listDocuments: vi.fn(),
      uploadDocument: vi.fn(),
    },
  };
});

function createClientDocument(id: string, overrides: Partial<ClientDocument> = {}): ClientDocument {
  return {
    documentId: id,
    title: `Document ${id}`,
    courseTitle: 'CS 101',
    lessonTitle: 'Module 1',
    sourceType: 'slm',
    program: 'BSCS',
    academicYear: '2025-2026',
    courseCode: 'CS101',
    pageCount: 15,
    processingStatus: 'PROCESSED',
    hasOcrPages: true,
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

describe('useSlmStorage Hook', () => {
  beforeEach(() => {
    vi.mocked(documentsApi.listDocuments).mockReset();
  });

  it('fetches SLM documents and computes repository metrics correctly', async () => {
    const mockResponse: DocumentListResponse = {
      items: [
        createClientDocument('doc-1', { program: 'BSCS', pageCount: 20, hasOcrPages: true }),
        createClientDocument('doc-2', { program: 'BSInfoTech', pageCount: 30, hasOcrPages: false }),
      ],
      total: 2,
      page: 1,
      pageSize: 10,
      stats: { total: 2, ready: 2, processing: 0, failed: 0 },
    };
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(mockResponse);

    const wrapper = createQueryWrapper();
    const { result } = renderHook(() => useSlmStorage(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.documents).toHaveLength(2);
    expect(result.current.metrics.totalModules).toBe(2);
    expect(result.current.metrics.totalIndexedPages).toBe(50);
    expect(result.current.metrics.bscsCount).toBe(1);
    expect(result.current.metrics.bsInfoTechCount).toBe(1);
    expect(result.current.metrics.ocrVerifiedCount).toBe(1);

    expect(documentsApi.listDocuments).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceType: 'slm',
        page: 1,
        pageSize: 10,
      }),
    );
  });

  it('updates program filter and resets page to 1', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [],
      total: 25,
      page: 1,
      pageSize: 10,
      stats: { total: 25, ready: 25, processing: 0, failed: 0 },
    });

    const wrapper = createQueryWrapper();
    const { result } = renderHook(() => useSlmStorage(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.setPage(2);
    });
    expect(result.current.page).toBe(2);

    act(() => {
      result.current.setProgramFilter('BSCS');
    });

    expect(result.current.programFilter).toBe('BSCS');
    expect(result.current.page).toBe(1);
  });

  it('manages modal and drawer states and invalidates queries on upload complete', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pageSize: 10,
      stats: { total: 0, ready: 0, processing: 0, failed: 0 },
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useSlmStorage(), { wrapper });

    const dummyDoc = createClientDocument('doc-99');

    act(() => {
      result.current.setInspectingDoc(dummyDoc);
      result.current.setIsUploadOpen(true);
    });

    expect(result.current.inspectingDoc?.documentId).toBe('doc-99');
    expect(result.current.isUploadOpen).toBe(true);

    act(() => {
      result.current.handleUploadComplete();
    });

    expect(result.current.isUploadOpen).toBe(false);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['slm-storage-repository'] });
  });
});
