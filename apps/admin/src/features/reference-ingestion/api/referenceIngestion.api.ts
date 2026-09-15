import { requestJson } from '@/shared/api/http';
import {
  mapDocumentUploadResponse,
  type RawDocumentUploadResponse,
} from '@/shared/types/documents';
import type { AdminUploadInput } from '../types';

export const CANONICAL_REFERENCE_PROGRAMS = ['BSCS', 'BSInfoTech'] as const;
export type CanonicalReferenceProgram = (typeof CANONICAL_REFERENCE_PROGRAMS)[number];

export function isCanonicalReferenceProgram(
  program?: string | null,
): program is CanonicalReferenceProgram {
  if (!program) return false;
  return program === 'BSCS' || program === 'BSInfoTech';
}

export const referenceIngestionApi = {
  uploadReferenceDocument: async (input: AdminUploadInput) => {
    const formData = new FormData();
    formData.append('file', input.file);
    formData.append('source_type', input.sourceType);
    formData.append('title', input.title.trim());

    if (input.sourceType === 'curriculum') {
      const trimmed = input.program?.trim();
      if (!trimmed || !isCanonicalReferenceProgram(trimmed)) {
        throw new Error(
          `Invalid curriculum program '${input.program}'. Must be exact canonical 'BSCS' or 'BSInfoTech'.`,
        );
      }
      formData.append('program', trimmed);
    } else if (input.program && input.program.trim()) {
      const trimmed = input.program.trim();
      if (!isCanonicalReferenceProgram(trimmed)) {
        throw new Error(
          `Invalid reference program '${input.program}'. Must be exact canonical 'BSCS' or 'BSInfoTech'.`,
        );
      }
      formData.append('program', trimmed);
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
