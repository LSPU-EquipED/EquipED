import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api/admin.api';

export function useAdminSummary() {
  return useQuery({
    queryKey: ['adminSummary'],
    queryFn: () => adminApi.getSummary(),
  });
}
