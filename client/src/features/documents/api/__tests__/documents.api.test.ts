import { describe, expect, it, vi, beforeEach } from 'vitest';
import { documentsApi } from '@/shared/api/documents.api';
import { requestJson } from '@/shared/api/http';
import type { RawDocumentListResponse } from '@/shared/types/documents';

vi.mock('@/shared/api/http', () => ({
  requestJson: vi.fn(),
  getErrorMessage: vi.fn((err: unknown) => String(err)),
}));

describe('documentsApi.listDocuments', () => {
  beforeEach(() => {
    vi.mocked(requestJson).mockReset();
  });

  it('builds query without params when empty', async () => {
    const mockResponse: RawDocumentListResponse = {
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
    };
    vi.mocked(requestJson).mockResolvedValueOnce(mockResponse);

    const result = await documentsApi.listDocuments();

    expect(requestJson).toHaveBeenCalledWith('/documents');
    expect(result).toEqual({
      items: [],
      total: 0,
      page: 1,
      pageSize: 10,
      stats: undefined,
    });
  });

  it('correctly maps page, page_size, source_type, program, search, and status query parameters', async () => {
    const mockResponse: RawDocumentListResponse = {
      items: [
        {
          document_id: 'doc-101',
          title: 'Advanced Operating Systems SLM',
          course_title: 'CS 301',
          lesson_title: 'Module 1',
          source_type: 'slm',
          program: 'BSCS',
          academic_year: '2025-2026',
          course_code: 'CS301',
          page_count: 24,
          processing_status: 'PROCESSED',
          has_ocr_pages: false,
          uploaded_at: '2026-08-18T08:00:00Z',
        },
      ],
      total: 25,
      page: 2,
      page_size: 10,
      stats: {
        total: 25,
        ready: 20,
        processing: 4,
        failed: 1,
      },
    };
    vi.mocked(requestJson).mockResolvedValueOnce(mockResponse);

    const result = await documentsApi.listDocuments({
      sourceType: 'slm',
      program: 'BSCS',
      page: 2,
      pageSize: 10,
      search: 'Operating Systems',
      status: 'ready',
    });

    expect(requestJson).toHaveBeenCalledWith(
      '/documents?source_type=slm&program=BSCS&page=2&page_size=10&search=Operating+Systems&status=ready',
    );
    expect(result.total).toBe(25);
    expect(result.page).toBe(2);
    expect(result.pageSize).toBe(10);
    expect(result.items).toHaveLength(1);
    expect(result.items[0].documentId).toBe('doc-101');
    expect(result.items[0].title).toBe('Advanced Operating Systems SLM');
    expect(result.stats).toEqual({
      total: 25,
      ready: 20,
      processing: 4,
      failed: 1,
    });
  });

  it('supports status query param for processing and failed states', async () => {
    const mockResponse: RawDocumentListResponse = {
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      stats: { total: 5, ready: 3, processing: 2, failed: 0 },
    };
    vi.mocked(requestJson).mockResolvedValueOnce(mockResponse);

    await documentsApi.listDocuments({
      status: 'processing',
    });

    expect(requestJson).toHaveBeenCalledWith('/documents?status=processing');

    vi.mocked(requestJson).mockResolvedValueOnce(mockResponse);
    await documentsApi.listDocuments({
      status: 'failed',
    });

    expect(requestJson).toHaveBeenCalledWith('/documents?status=failed');
  });
});
