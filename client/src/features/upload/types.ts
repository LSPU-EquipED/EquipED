import type { DocumentSourceType, DocumentUploadResponse } from '@/shared/types/documents';

export type UploadProgramId = 'bsit' | 'bscs' | 'bsis';

export type UploadDocumentInput = {
  file: File;
  sourceType: DocumentSourceType;
  title: string;
  courseTitle?: string | null;
  lessonTitle?: string | null;
  program?: string | null;
};

export type UploadDocumentResult = DocumentUploadResponse;
