import { useQuery } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useCourses() {
  return useQuery({
    queryKey: ['curriculum-map', 'courses'],
    queryFn: () => curriculumAlignmentApi.listCourses(),
  });
}
