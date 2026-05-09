import { requestJson } from '@/shared/api/http';
import type { AuthCredentials, AuthStateResponse } from '../types';

async function login(credentials: AuthCredentials) {
  return requestJson<AuthStateResponse>('/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(credentials),
  });
}

async function me() {
  return requestJson<AuthStateResponse>('/auth/me');
}

async function logout() {
  return requestJson<AuthStateResponse>('/auth/logout', {
    method: 'POST',
  });
}

export const authApi = {
  login,
  me,
  logout,
};
