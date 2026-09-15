import { requestJson } from '@/shared/api/http';
import type { LatestEvaluationsResponse } from '@/shared/types/evaluations';

export function buildLatestEvaluationsQuery(documentIds: string[]): string {
  const deduped = Array.from(new Set(documentIds.filter(Boolean))).sort();
  const capped = deduped.slice(0, 100);
  if (capped.length === 0) {
    return '/evaluations/latest';
  }
  const searchParams = new URLSearchParams();
  for (const id of capped) {
    searchParams.append('document_id', id);
  }
  return `/evaluations/latest?${searchParams.toString()}`;
}

async function getLatestEvaluations(documentIds: string[]): Promise<LatestEvaluationsResponse> {
  const deduped = Array.from(new Set(documentIds.filter(Boolean))).sort();
  const capped = deduped.slice(0, 100);
  if (capped.length === 0) {
    return { items: [] };
  }
  const url = buildLatestEvaluationsQuery(capped);
  return requestJson<LatestEvaluationsResponse>(url);
}

export const evaluationsApi = {
  getLatestEvaluations,
  buildLatestEvaluationsQuery,
};
