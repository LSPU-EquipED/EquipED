import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api/admin.api';

export function useAdminMatrix(params: { program?: string; status?: string; page?: number; page_size?: number } = {}) {
  return useQuery({
    queryKey: ['admin-matrix', params],
    queryFn: () => adminApi.getMatrix(params),
  });
}
