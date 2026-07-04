import { requestJson } from '@/shared/api/http';
import {
  mapDocumentUploadResponse,
  type RawDocumentUploadResponse,
} from '@/shared/types/documents';
import type { UploadDocumentInput, UploadDocumentResult } from '../types';

async function uploadDocument(input: UploadDocumentInput): Promise<UploadDocumentResult> {
  const formData = new FormData();
  formData.append('file', input.file);
  formData.append('source_type', input.sourceType);
  formData.append('title', input.title.trim());

  const response = await requestJson<RawDocumentUploadResponse>('/documents/upload', {
    method: 'POST',
    body: formData,
  });

  return mapDocumentUploadResponse(response);
}

export const uploadApi = {
  uploadDocument,
};
