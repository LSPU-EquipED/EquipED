import { requestJson } from '@/shared/api/http';
import type {
  AlignmentCheck,
  CourseListResponse,
  DocumentPagesResponse,
} from '../types';

export const curriculumAlignmentApi = {
  listCourses: async (): Promise<CourseListResponse> => {
    return requestJson<CourseListResponse>('/curriculum-map/courses');
  },

  runCheck: async (documentId: string, courseId: string): Promise<AlignmentCheck> => {
    return requestJson<AlignmentCheck>('/curriculum-map/checks', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, course_id: courseId }),
    });
  },

  getCheck: async (checkId: string): Promise<AlignmentCheck> => {
    return requestJson<AlignmentCheck>(`/curriculum-map/checks/${checkId}`);
  },

  getDocumentPages: async (checkId: string): Promise<DocumentPagesResponse> => {
    return requestJson<DocumentPagesResponse>(`/curriculum-map/checks/${checkId}/document-pages`);
  },
};
