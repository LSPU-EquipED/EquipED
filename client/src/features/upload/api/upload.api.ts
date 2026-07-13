import { documentsApi } from '@/shared/api/documents.api';
import type { UploadDocumentInput, UploadDocumentResult } from '../types';

async function uploadDocument(input: UploadDocumentInput): Promise<UploadDocumentResult> {
  return documentsApi.uploadDocument(input);
}

export const uploadApi = {
  uploadDocument,
};
