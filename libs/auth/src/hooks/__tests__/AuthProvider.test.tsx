import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React, { type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../AuthProvider';
import { useAuth } from '../useAuth';
import * as authApiModule from '../../api/auth.api';

vi.mock('../../api/auth.api', () => ({
  authApi: {
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    forgotPassword: vi.fn(),
  },
}));

describe('AuthProvider & useAuth', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
  });

  function createWrapper() {
    return function Wrapper({ children }: { children: ReactNode }) {
      return (
        <QueryClientProvider client={queryClient}>
          <AuthProvider>{children}</AuthProvider>
        </QueryClientProvider>
      );
    };
  }

  it('hydrates authenticated user from server session query', async () => {
    const mockUser = {
      id: 'faculty-1',
      displayName: 'Faculty Jane',
      email: 'jane@lspu.edu.ph',
      role: 'faculty' as const,
      evaluatorPermissions: ['sme'],
    };

    vi.mocked(authApiModule.authApi.me).mockResolvedValueOnce({
      authenticated: true,
      user: mockUser,
    });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });

    // Initially provisional
    expect(result.current.ready).toBe(false);
    expect(result.current.status).toBe('anonymous');
    expect(result.current.source).toBe('provisional');

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.status).toBe('authenticated');
    expect(result.current.source).toBe('server');
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.error).toBeNull();
  });

  it('hydrates anonymous state when server returns authenticated: false', async () => {
    vi.mocked(authApiModule.authApi.me).mockResolvedValueOnce({
      authenticated: false,
      user: null,
    });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.status).toBe('anonymous');
    expect(result.current.source).toBe('server');
    expect(result.current.user).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('handles session query failure by falling back to anonymous state with error', async () => {
    vi.mocked(authApiModule.authApi.me).mockRejectedValueOnce(
      new Error('Session validation failed'),
    );

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    expect(result.current.status).toBe('anonymous');
    expect(result.current.source).toBe('server');
    expect(result.current.user).toBeNull();
    expect(result.current.error).toBe('Session validation failed');

    // clearError clears the session error
    act(() => {
      result.current.clearError();
    });
    expect(result.current.error).toBeNull();
  });

  it('updates state on successful login', async () => {
    vi.mocked(authApiModule.authApi.me).mockResolvedValueOnce({
      authenticated: false,
      user: null,
    });

    const mockLoggedInUser = {
      id: 'admin-1',
      displayName: 'Admin User',
      email: 'admin@lspu.edu.ph',
      role: 'admin' as const,
    };

    vi.mocked(authApiModule.authApi.login).mockResolvedValueOnce({
      authenticated: true,
      user: mockLoggedInUser,
    });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    await act(async () => {
      await result.current.login({ email: 'admin@lspu.edu.ph', password: 'password123' });
    });

    expect(result.current.status).toBe('authenticated');
    expect(result.current.user).toEqual(mockLoggedInUser);
    expect(result.current.error).toBeNull();
  });

  it('handles login failure and sets error state', async () => {
    vi.mocked(authApiModule.authApi.me).mockResolvedValueOnce({
      authenticated: false,
      user: null,
    });

    vi.mocked(authApiModule.authApi.login).mockRejectedValueOnce(
      new Error('Invalid credentials'),
    );

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    await act(async () => {
      try {
        await result.current.login({ email: 'bad@lspu.edu.ph', password: 'wrong' });
      } catch {
        // Expected throw
      }
    });

    expect(result.current.status).toBe('anonymous');
    expect(result.current.user).toBeNull();
    expect(result.current.error).toBe('Invalid credentials');
  });

  it('clears session on logout', async () => {
    const mockUser = {
      id: 'faculty-1',
      displayName: 'Faculty Jane',
      email: 'jane@lspu.edu.ph',
      role: 'faculty' as const,
    };

    vi.mocked(authApiModule.authApi.me).mockResolvedValueOnce({
      authenticated: true,
      user: mockUser,
    });

    vi.mocked(authApiModule.authApi.logout).mockResolvedValueOnce({
      authenticated: false,
      user: null,
    });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.status).toBe('authenticated');
    });

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.status).toBe('anonymous');
    expect(result.current.user).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('refreshes session correctly on refresh() call', async () => {
    vi.mocked(authApiModule.authApi.me).mockResolvedValueOnce({
      authenticated: false,
      user: null,
    });

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });

    const refreshedUser = {
      id: 'faculty-2',
      displayName: 'Faculty Two',
      email: 'f2@lspu.edu.ph',
      role: 'faculty' as const,
    };

    vi.mocked(authApiModule.authApi.me).mockResolvedValueOnce({
      authenticated: true,
      user: refreshedUser,
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.status).toBe('authenticated');
    expect(result.current.user).toEqual(refreshedUser);
  });
});
