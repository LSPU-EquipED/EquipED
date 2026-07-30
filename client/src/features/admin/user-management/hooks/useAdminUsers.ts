import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { userManagementApi } from '../api/userManagement.api';
import type { AdminUserCreateBody, AdminUserUpdateBody } from '../types';

export function useAdminUsers() {
  return useQuery({
    queryKey: ['adminUsers'],
    queryFn: () => userManagementApi.getUsers(),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: AdminUserCreateBody) => userManagementApi.createUser(body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, body }: { userId: string; body: AdminUserUpdateBody }) =>
      userManagementApi.updateUser(userId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => userManagementApi.deactivateUser(userId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}

export function useHardDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => userManagementApi.hardDeleteUser(userId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}
