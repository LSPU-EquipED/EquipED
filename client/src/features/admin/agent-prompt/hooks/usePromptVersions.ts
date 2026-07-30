import { useQuery } from '@tanstack/react-query';
import { agentPromptApi } from '../api/agentPrompt.api';

export function usePromptVersions(agentId: string) {
  return useQuery({
    queryKey: ['promptVersions', agentId],
    queryFn: () => agentPromptApi.getPromptVersions(agentId),
    enabled: !!agentId,
  });
}
