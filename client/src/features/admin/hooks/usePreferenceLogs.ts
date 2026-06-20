import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api/admin.api';

export function usePreferenceLogs(
  params: { action?: string; page?: number; page_size?: number } = {},
) {
  return useQuery({
    queryKey: ['preferenceLogs', params],
    queryFn: () => adminApi.getPreferenceLogs(params),
  });
}
