import { requestJson } from './http';
import type {
  EvaluationListResponse,
  LatestEvaluationsResponse,
  TargetAgent,
} from '@equiped/types';

export interface ListEvaluationsOptions {
  documentId?: string;
  targetAgent?: TargetAgent | 'all';
  status?: string;
  page?: number;
  pageSize?: number;
}

export function buildListEvaluationsQuery(options: ListEvaluationsOptions = {}): string {
  const params = new URLSearchParams();
  if (options.documentId) params.set('document_id', options.documentId);
  if (options.targetAgent) params.set('target_agent', options.targetAgent);
  if (options.status) params.set('status', options.status);
  if (options.page) params.set('page', String(options.page));
  if (options.pageSize) params.set('page_size', String(options.pageSize));
  const query = params.toString();
  return `/evaluations/${query ? `?${query}` : ''}`;
}

async function listEvaluations(
  options: ListEvaluationsOptions = {},
): Promise<EvaluationListResponse> {
  const url = buildListEvaluationsQuery(options);
  return requestJson<EvaluationListResponse>(url);
}

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
  listEvaluations,
  buildListEvaluationsQuery,
  getLatestEvaluations,
  buildLatestEvaluationsQuery,
};
