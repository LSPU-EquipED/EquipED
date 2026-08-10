import { useQuery } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useAlignmentCheckHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: ['curriculum-map', 'checks', page, pageSize],
    queryFn: () => curriculumAlignmentApi.listChecks(page, pageSize),
  });
}
