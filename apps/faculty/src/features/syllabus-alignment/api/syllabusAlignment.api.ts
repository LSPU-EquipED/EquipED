import { requestJson } from '@equiped/api-client';
import type {
  AlignmentRun,
  AlignmentSlmListResponse,
  SyllabusReferenceOptionsResponse,
} from '../types';

export const alignmentApi = {
  listSlms: async (
    page = 1,
    pageSize = 20,
    options?: { search?: string; status_filter?: string },
  ): Promise<AlignmentSlmListResponse> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (options?.search) params.set('search', options.search);
    if (options?.status_filter) params.set('status_filter', options.status_filter);
    return requestJson<AlignmentSlmListResponse>(`/syllabus-alignments/slms?${params.toString()}`);
  },

  getCurrent: (slmDocumentId: string) =>
    requestJson<AlignmentRun | null>(
      `/syllabus-alignments/current?slm_document_id=${encodeURIComponent(slmDocumentId)}`,
    ),

  getRun: (alignmentId: string) =>
    requestJson<AlignmentRun>(`/syllabus-alignments/${alignmentId}`),

  start: (slmDocumentId: string, syllabusDocumentId: string) =>
    requestJson<AlignmentRun>('/syllabus-alignments', {
      method: 'POST',
      body: JSON.stringify({
        slm_document_id: slmDocumentId,
        syllabus_document_id: syllabusDocumentId,
      }),
    }),

  getAvailableSyllabi: () =>
    requestJson<SyllabusReferenceOptionsResponse>('/documents/syllabi/available'),
};
