import { useQuery } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useAlignmentCheck(checkId: string | null) {
  return useQuery({
    queryKey: ['curriculum-map', 'check', checkId],
    queryFn: () => curriculumAlignmentApi.getCheck(checkId as string),
    enabled: !!checkId,
  });
}
