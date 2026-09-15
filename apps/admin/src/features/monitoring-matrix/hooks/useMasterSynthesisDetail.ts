import { useQuery } from '@tanstack/react-query';
import { matrixApi } from '../api/matrix.api';

export function useMasterSynthesisDetail(documentId: string) {
  return useQuery({
    queryKey: ['matrix-detail', documentId],
    queryFn: () => matrixApi.getMasterSynthesisDetail(documentId),
    enabled: Boolean(documentId),
  });
}
