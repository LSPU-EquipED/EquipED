import { useQuery } from '@tanstack/react-query';
import { homeApi } from '../api/home.api';

export function useAdminMatrix(
  params: { program?: string; status?: string; page?: number; page_size?: number } = {},
) {
  return useQuery({
    queryKey: ['admin-matrix', params],
    queryFn: () => homeApi.getMatrix(params),
  });
}
