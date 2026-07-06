import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '@/shared/api/http';
import { adminApi } from '../api/admin.api';

const QUERY_KEY = ['adminReferences'];

export function useReferenceLibrary() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => adminApi.getReferences(),
  });
}

export function useDeleteReference() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => adminApi.deleteReference(documentId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useRebuildReferenceEmbeddings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => adminApi.rebuildReferenceEmbeddings(documentId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function getReferenceFileUrl(documentId: string): string {
  return adminApi.getReferenceFileUrl(documentId);
}

export function getReferenceOperationError(error: unknown): string {
  return getErrorMessage(error, 'Operation failed. Please try again.');
}
