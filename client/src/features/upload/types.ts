import type { DocumentSourceType, DocumentUploadResponse } from '@/shared/types/documents';

export type UploadDocumentInput = {
  file: File;
  sourceType: DocumentSourceType;
  title: string;
  program?: string;
};

export type UploadDocumentResult = DocumentUploadResponse;
