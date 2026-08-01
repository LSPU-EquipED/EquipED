import { useMutation, useQueryClient } from '@tanstack/react-query';
import { curriculumAlignmentApi } from '../api/curriculumAlignment.api';

export function useDeleteAlignmentCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (checkId: string) => curriculumAlignmentApi.deleteCheck(checkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['curriculum-map', 'checks'] });
    },
  });
}
