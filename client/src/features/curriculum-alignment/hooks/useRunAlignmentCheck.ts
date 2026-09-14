import { useMutation } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useRunAlignmentCheck() {
  return useMutation({
    mutationFn: ({ documentId, courseId }: { documentId: string; courseId: string }) =>
      curriculumAlignmentApi.runCheck(documentId, courseId),
  });
}
