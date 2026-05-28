import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api/admin.api';
import type { AdminUserCreateBody } from '../types';

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
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });
}
