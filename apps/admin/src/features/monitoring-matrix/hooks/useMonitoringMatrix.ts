import { useQuery } from '@tanstack/react-query';
import { matrixApi } from '../api/matrix.api';

export function useMonitoringMatrix(
  params: { program?: string; status?: string; page?: number; page_size?: number } = {},
) {
  return useQuery({
    queryKey: ['matrix', params],
    queryFn: () => matrixApi.getMatrix(params),
  });
}
