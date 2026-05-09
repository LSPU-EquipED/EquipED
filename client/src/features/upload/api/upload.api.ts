import { requestJson } from '@/shared/api/http';
import { mapDocumentUploadResponse, type RawDocumentUploadResponse } from '@/shared/types/documents';
import type { UploadDocumentInput, UploadDocumentResult } from '../types';

async function uploadDocument(input: UploadDocumentInput): Promise<UploadDocumentResult> {
  const formData = new FormData();
  formData.append('file', input.file);
  formData.append('source_type', input.sourceType);
  formData.append('title', input.title.trim());

  if (input.courseTitle?.trim()) {
    formData.append('course_title', input.courseTitle.trim());
  }

  if (input.lessonTitle?.trim()) {
    formData.append('lesson_title', input.lessonTitle.trim());
  }

  if (input.program?.trim()) {
    formData.append('program', input.program.trim());
  }

  const response = await requestJson<RawDocumentUploadResponse>('/documents/upload', {
    method: 'POST',
    body: formData,
  });

  return mapDocumentUploadResponse(response);
}

export const uploadApi = {
  uploadDocument,
};
