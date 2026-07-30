import { requestJson } from '@/shared/api/http';
import {
  mapDocumentUploadResponse,
  type RawDocumentUploadResponse,
} from '@/shared/types/documents';
import type { AdminUploadInput } from '../types';

export const referenceIngestionApi = {
  uploadReferenceDocument: async (input: AdminUploadInput) => {
    const formData = new FormData();
    formData.append('file', input.file);
    formData.append('source_type', input.sourceType);
    formData.append('title', input.title.trim());

    if (input.program && input.program.trim()) {
      formData.append('program', input.program.trim().toUpperCase());
    }

    if (input.sourceType === 'policy' && input.policyArea) {
      formData.append('policy_area', input.policyArea);
    }

    const response = await requestJson<RawDocumentUploadResponse>('/documents/upload', {
      method: 'POST',
      body: formData,
    });

    return mapDocumentUploadResponse(response);
  },
};
