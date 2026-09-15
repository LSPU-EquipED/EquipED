import { describe, expect, it, vi } from 'vitest';
import * as httpModule from '@/shared/api/http';
import { buildLatestEvaluationsQuery, evaluationsApi } from '../evaluations.api';

describe('evaluationsApi.buildLatestEvaluationsQuery', () => {
  it('encodes repeated document_id query parameters', () => {
    const url = buildLatestEvaluationsQuery(['doc-1', 'doc-2']);
    expect(url).toBe('/evaluations/latest?document_id=doc-1&document_id=doc-2');
  });

  it('deduplicates and sorts document IDs for stable query URLs', () => {
    const url = buildLatestEvaluationsQuery(['doc-b', 'doc-a', 'doc-b', 'doc-a']);
    expect(url).toBe('/evaluations/latest?document_id=doc-a&document_id=doc-b');
  });

  it('filters out falsy or empty values', () => {
    const url = buildLatestEvaluationsQuery(['doc-1', '', 'doc-2']);
    expect(url).toBe('/evaluations/latest?document_id=doc-1&document_id=doc-2');
  });

  it('caps at 100 document IDs', () => {
    const ids = Array.from({ length: 150 }, (_, i) => `doc-${i.toString().padStart(3, '0')}`);
    const url = buildLatestEvaluationsQuery(ids);
    const params = new URLSearchParams(url.replace('/evaluations/latest?', ''));
    expect(params.getAll('document_id')).toHaveLength(100);
  });

  it('returns base URL when given empty list', () => {
    expect(buildLatestEvaluationsQuery([])).toBe('/evaluations/latest');
  });
});

describe('evaluationsApi.getLatestEvaluations', () => {
  it('returns empty items immediately without HTTP call if given empty list', async () => {
    const spy = vi.spyOn(httpModule, 'requestJson');
    const result = await evaluationsApi.getLatestEvaluations([]);
    expect(result).toEqual({ items: [] });
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it('calls requestJson with properly formatted URL when document IDs are present', async () => {
    const mockResponse = {
      items: [
        {
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          status: 'COMPLETED',
          submitted_at: '2026-08-20T10:00:00Z',
        },
      ],
    };
    const spy = vi.spyOn(httpModule, 'requestJson').mockResolvedValueOnce(mockResponse);

    const result = await evaluationsApi.getLatestEvaluations(['doc-1']);
    expect(spy).toHaveBeenCalledWith('/evaluations/latest?document_id=doc-1');
    expect(result).toEqual(mockResponse);
    spy.mockRestore();
  });
});
