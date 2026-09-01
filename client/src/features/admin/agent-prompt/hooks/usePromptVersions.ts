import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentPromptApi } from '../api/agentPrompt.api';
import type { PromptCreateBody } from '../types';

export function usePromptVersions(agentId: string) {
  return useQuery({
    queryKey: ['promptVersions', agentId],
    queryFn: () => agentPromptApi.getPromptVersions(agentId),
    enabled: !!agentId,
  });
}

export function useCreatePrompt(agentId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: PromptCreateBody) => agentPromptApi.createPrompt(agentId, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['promptVersions', agentId] });
    },
  });
}

export function useRevertPrompt(agentId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (versionId: string) => agentPromptApi.revertPrompt(agentId, versionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['promptVersions', agentId] });
    },
  });
}
