import { requestJson } from '@/shared/api/http';
import { mapDocumentListResponse, type DocumentListResponse, type RawDocumentListResponse } from '@/shared/types/documents';

type ListDocumentsParams = {
  sourceType?: string;
  program?: string;
  page?: number;
  pageSize?: number;
};

function buildQuery(params: ListDocumentsParams) {
  const searchParams = new URLSearchParams();

  if (params.sourceType) {
    searchParams.set('source_type', params.sourceType);
  }

  if (params.program) {
    searchParams.set('program', params.program);
  }

  if (params.page) {
    searchParams.set('page', String(params.page));
  }

  if (params.pageSize) {
    searchParams.set('page_size', String(params.pageSize));
  }

  const query = searchParams.toString();
  return query ? `/documents?${query}` : '/documents';
}

async function listDocuments(params: ListDocumentsParams = {}): Promise<DocumentListResponse> {
  const response = await requestJson<RawDocumentListResponse>(buildQuery(params));
  return mapDocumentListResponse(response);
}

export const dashboardApi = {
  listDocuments,
};
