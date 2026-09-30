import { useQuery } from '@tanstack/react-query';
import { preferenceLogApi } from '../api/preferenceLog.api';
import type { PreferenceLogListParams } from '../types';

export function usePreferenceLogs(
  params: PreferenceLogListParams = {},
) {
  return useQuery({
    queryKey: ['preferenceLogs', params],
    queryFn: () => preferenceLogApi.getPreferenceLogs(params),
  });
}
