import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '@/shared/api/http';
import { referenceLibraryApi } from '../api/referenceLibrary.api';

const QUERY_KEY = ['adminReferences'];
const POLICY_QUERY_KEY = ['adminPolicies'];

export function useReferenceLibrary() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => referenceLibraryApi.getReferences(),
  });
}

export function useDeleteReference() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => referenceLibraryApi.deleteReference(documentId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useRebuildReferenceEmbeddings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => referenceLibraryApi.rebuildReferenceEmbeddings(documentId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function usePolicyLibrary() {
  return useQuery({
    queryKey: POLICY_QUERY_KEY,
    queryFn: () => referenceLibraryApi.getPolicies(),
  });
}

export function useDeletePolicy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => referenceLibraryApi.deletePolicy(documentId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: POLICY_QUERY_KEY });
    },
  });
}

export function useRebuildPolicyEmbeddings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => referenceLibraryApi.rebuildPolicyEmbeddings(documentId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: POLICY_QUERY_KEY });
    },
  });
}

export function getReferenceFileUrl(documentId: string): string {
  return referenceLibraryApi.getReferenceFileUrl(documentId);
}

export function getReferenceOperationError(error: unknown): string {
  return getErrorMessage(error, 'Operation failed. Please try again.');
}
