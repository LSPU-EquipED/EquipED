import { requestJson } from '@/shared/api/http';
import {
  mapDocumentUploadResponse,
  mapDocumentListResponse,
  mapDocumentResponse,
  type ClientDocument,
  type DocumentListResponse,
  type RawDocumentListResponse,
  type RawDocumentResponse,
  type RawDocumentUploadResponse,
  type DocumentSourceType,
  type DocumentUploadResponse,
} from '@/shared/types/documents';

type ListDocumentsParams = {
  sourceType?: string;
  program?: string;
  page?: number;
  pageSize?: number;
};

type UploadDocumentInput = {
  file: File;
  sourceType: DocumentSourceType;
  title: string;
  program?: string;
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

async function uploadDocument(input: UploadDocumentInput): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', input.file);
  formData.append('source_type', input.sourceType);
  formData.append('title', input.title.trim());
  if (input.program?.trim()) {
    formData.append('program', input.program.trim());
  }

  const response = await requestJson<RawDocumentUploadResponse>('/documents/upload', {
    method: 'POST',
    body: formData,
  });
  return mapDocumentUploadResponse(response);
}

export const documentsApi = {
  getDocument,
  listDocuments,
  uploadDocument,
};

export type { ListDocumentsParams, UploadDocumentInput };
