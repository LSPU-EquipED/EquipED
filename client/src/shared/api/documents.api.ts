import { requestJson } from '@/shared/api/http';
import {
  mapDocumentListResponse,
  mapDocumentResponse,
  type ClientDocument,
  type DocumentListResponse,
  type RawDocumentListResponse,
  type RawDocumentResponse,
} from '@/shared/types/documents';

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

async function getDocument(documentId: string): Promise<ClientDocument> {
  const response = await requestJson<RawDocumentResponse>(`/documents/${documentId}`);
  return mapDocumentResponse(response);
}

export const documentsApi = {
  getDocument,
  listDocuments,
};

export type { ListDocumentsParams };
