import { useQuery } from '@tanstack/react-query';
import { preferenceLogApi } from '../api/preferenceLog.api';

export function usePreferenceLogs(
  params: { action?: string; page?: number; page_size?: number } = {},
) {
  return useQuery({
    queryKey: ['preferenceLogs', params],
    queryFn: () => preferenceLogApi.getPreferenceLogs(params),
  });
}
