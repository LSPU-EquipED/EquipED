import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api/admin.api';

export function usePromptVersions(agentId: string) {
  return useQuery({
    queryKey: ['promptVersions', agentId],
    queryFn: () => adminApi.getPromptVersions(agentId),
    enabled: !!agentId,
  });
}
