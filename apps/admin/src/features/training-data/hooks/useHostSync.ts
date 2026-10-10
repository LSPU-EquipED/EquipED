import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

const KEY = ['hostSync'] as const;

export function useHostSync() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => trainingDataApi.getHostSync(),
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
}

export function useCreateHostKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => trainingDataApi.createHostKey(),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function useRevokeHostKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => trainingDataApi.revokeHostKey(),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
