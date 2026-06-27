import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api/admin.api';
import type { AdminUserCreateBody, AdminUserUpdateBody } from '../types';

export function useAdminUsers() {
  return useQuery({
    queryKey: ['adminUsers'],
    queryFn: () => adminApi.getUsers(),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: AdminUserCreateBody) => adminApi.createUser(body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, body }: { userId: string; body: AdminUserUpdateBody }) =>
      adminApi.updateUser(userId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => adminApi.deactivateUser(userId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}

export function useHardDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => adminApi.hardDeleteUser(userId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}
