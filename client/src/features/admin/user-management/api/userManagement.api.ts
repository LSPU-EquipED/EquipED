import { requestJson } from '@/shared/api/http';
import type {
  AdminUserCreateBody,
  AdminUserListResponse,
  AdminUserResponse,
  AdminUserUpdateBody,
} from '../types';

export const userManagementApi = {
  getUsers: () => requestJson<AdminUserListResponse>('/admin/users'),

  createUser: (body: AdminUserCreateBody) =>
    requestJson<AdminUserResponse>('/admin/users', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateUser: (userId: string, body: AdminUserUpdateBody) =>
    requestJson<AdminUserResponse>(`/admin/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deactivateUser: (userId: string) =>
    requestJson<void>(`/admin/users/${userId}`, {
      method: 'DELETE',
    }),

  hardDeleteUser: (userId: string) =>
    requestJson<void>(`/admin/users/${userId}/permanent`, {
      method: 'DELETE',
  }),

  setApproval: (userId: string, account_status: AdminUserResponse['account_status']) =>
    requestJson<AdminUserResponse>(`/admin/users/${userId}/approval`, {
      method: 'POST', body: JSON.stringify({ status: account_status }),
    }),
};
