import { describe, expect, it, vi } from 'vitest';
import * as httpModule from '../http';
import {
  evaluationsApi,
  buildListEvaluationsQuery,
  buildLatestEvaluationsQuery,
} from '../evaluations.api';

describe('evaluations.api query builders', () => {
  it('buildListEvaluationsQuery constructs correct URLs with search parameters', () => {
    expect(buildListEvaluationsQuery()).toBe('/evaluations/');
    expect(
      buildListEvaluationsQuery({
        documentId: 'doc-123',
        targetAgent: 'sme',
        status: 'COMPLETED',
        page: 2,
        pageSize: 15,
      }),
    ).toBe(
      '/evaluations/?document_id=doc-123&target_agent=sme&status=COMPLETED&page=2&page_size=15',
    );
  });

  it('buildLatestEvaluationsQuery deduplicates and formats document_id queries', () => {
    expect(buildLatestEvaluationsQuery([])).toBe('/evaluations/latest');
    expect(
      buildLatestEvaluationsQuery(['doc-2', 'doc-1', 'doc-2']),
    ).toBe('/evaluations/latest?document_id=doc-1&document_id=doc-2');
  });
});

describe('evaluations.api transport calls', () => {
  it('listEvaluations calls requestJson with built query url', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      page: 1,
      pageSize: 20,
    };
    const spy = vi.spyOn(httpModule, 'requestJson').mockResolvedValueOnce(mockResponse);

    const result = await evaluationsApi.listEvaluations({
      documentId: 'doc-abc',
      page: 1,
      pageSize: 10,
    });

    expect(spy).toHaveBeenCalledWith('/evaluations/?document_id=doc-abc&page=1&page_size=10');
    expect(result).toEqual(mockResponse);

    spy.mockRestore();
  });

  it('getLatestEvaluations returns empty items without making a request when documentIds is empty', async () => {
    const spy = vi.spyOn(httpModule, 'requestJson');

    const result = await evaluationsApi.getLatestEvaluations([]);

    expect(spy).not.toHaveBeenCalled();
    expect(result).toEqual({ items: [] });

    spy.mockRestore();
  });

  it('getLatestEvaluations deduplicates, caps at 100 IDs, and calls requestJson', async () => {
    const mockResponse = { items: [] };
    const spy = vi.spyOn(httpModule, 'requestJson').mockResolvedValueOnce(mockResponse);

    // Create array with duplicates and more than 100 items (e.g. 110 unique IDs)
    const ids: string[] = [];
    for (let i = 1; i <= 110; i++) {
      ids.push(`doc-${String(i).padStart(3, '0')}`);
    }
    // Add duplicates
    ids.push('doc-001', 'doc-002');

    const result = await evaluationsApi.getLatestEvaluations(ids);

    expect(spy).toHaveBeenCalledTimes(1);
    const calledUrl = spy.mock.calls[0][0] as string;
    expect(calledUrl.startsWith('/evaluations/latest?')).toBe(true);

    const params = new URLSearchParams(calledUrl.replace('/evaluations/latest?', ''));
    const fetchedDocIds = params.getAll('document_id');
    expect(fetchedDocIds.length).toBe(100);
    // Since it's sorted, doc-001 should be first and doc-100 should be the 100th
    expect(fetchedDocIds[0]).toBe('doc-001');
    expect(fetchedDocIds[99]).toBe('doc-100');
    expect(result).toEqual(mockResponse);

    spy.mockRestore();
  });
});
