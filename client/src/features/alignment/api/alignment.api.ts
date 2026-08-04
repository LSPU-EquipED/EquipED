import { requestJson } from '@/shared/api/http';
import type {
  AlignmentRun,
  AlignmentSlmListResponse,
  SyllabusReferenceOptionsResponse,
} from '../types';

export const alignmentApi = {
  listSlms: (page = 1, pageSize = 100) =>
    requestJson<AlignmentSlmListResponse>(
      `/syllabus-alignments/slms?page=${page}&page_size=${pageSize}`,
    ),

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
