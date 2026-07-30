import { useQuery } from '@tanstack/react-query';
import { homeApi } from '../api/home.api';

export function useAdminSummary() {
  return useQuery({
    queryKey: ['adminSummary'],
    queryFn: () => homeApi.getSummary(),
  });
}
