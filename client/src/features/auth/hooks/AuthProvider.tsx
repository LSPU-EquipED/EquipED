import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { getErrorMessage } from '@/shared/api/http';
import { authApi } from '../api/auth.api';
import type { AppAuthContext, AppAuthUser, AuthCredentials, AuthStateResponse } from '../types';
import { AuthContext } from './useAuth';

const AUTH_SESSION_QUERY_KEY = ['auth', 'session'] as const;
const ANONYMOUS_AUTH_RESPONSE: AuthStateResponse = { authenticated: false, user: null };
const PREVIEW_AUTH_USER: AppAuthUser = {
  id: 'preview-admin',
  email: 'preview@equiped.local',
  displayName: 'Preview Admin',
  role: 'admin',
};

function getProvisionalState(): Omit<
  AppAuthContext,
  'login' | 'logout' | 'refresh' | 'clearError'
> {
  return {
    status: 'anonymous',
    source: 'provisional',
    ready: false,
    error: null,
    user: null,
  };
}

function getAuthenticatedState(
  user: AppAuthUser,
): Omit<AppAuthContext, 'login' | 'logout' | 'refresh' | 'clearError'> {
  return {
    status: 'authenticated',
    source: 'server',
    ready: true,
    error: null,
    user,
  };
}

function getAnonymousState(
  error: string | null = null,
): Omit<AppAuthContext, 'login' | 'logout' | 'refresh' | 'clearError'> {
  return {
    status: 'anonymous',
    source: 'server',
    ready: true,
    error,
    user: null,
  };
}

function resolveState(response: AuthStateResponse) {
  return response.authenticated && response.user
    ? getAuthenticatedState(response.user)
    : getAnonymousState();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [authError, setAuthError] = useState<string | null>(null);
  const [sessionErrorDismissed, setSessionErrorDismissed] = useState(false);
  const isPreviewAuth =
    import.meta.env.DEV && new URLSearchParams(window.location.search).get('previewAuth') === '1';
  const sessionQuery = useQuery({
    queryKey: AUTH_SESSION_QUERY_KEY,
    queryFn: authApi.me,
    retry: false,
    enabled: !isPreviewAuth,
  });

  const clearError = useCallback(() => {
    setAuthError(null);
    setSessionErrorDismissed(true);
  }, []);

  const refresh = useCallback(async () => {
    setAuthError(null);
    setSessionErrorDismissed(false);

    try {
      const response = await queryClient.fetchQuery({
        queryKey: AUTH_SESSION_QUERY_KEY,
        queryFn: authApi.me,
        retry: false,
      });

      queryClient.setQueryData(AUTH_SESSION_QUERY_KEY, response);
    } catch (error) {
      queryClient.setQueryData(AUTH_SESSION_QUERY_KEY, ANONYMOUS_AUTH_RESPONSE);
      setAuthError(getErrorMessage(error, 'Unable to restore your session.'));
    }
  }, [queryClient]);

  const login = useCallback(
    async (credentials: AuthCredentials) => {
      setAuthError(null);
      setSessionErrorDismissed(false);

      try {
        const response = await authApi.login(credentials);
        queryClient.setQueryData(AUTH_SESSION_QUERY_KEY, response);
      } catch (error) {
        queryClient.setQueryData(AUTH_SESSION_QUERY_KEY, ANONYMOUS_AUTH_RESPONSE);
        setAuthError(getErrorMessage(error, 'Unable to sign in.'));
        throw error;
      }
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      queryClient.setQueryData(AUTH_SESSION_QUERY_KEY, ANONYMOUS_AUTH_RESPONSE);
      setAuthError(null);
      setSessionErrorDismissed(false);
    }
  }, [queryClient]);

  const authState = useMemo<
    Omit<AppAuthContext, 'login' | 'logout' | 'refresh' | 'clearError'>
  >(() => {
    const resolvedState = (() => {
      if (isPreviewAuth) {
        return getAuthenticatedState(PREVIEW_AUTH_USER);
      }

      if (sessionQuery.isPending) {
        return getProvisionalState();
      }

      if (sessionQuery.isError) {
        return getAnonymousState(
          sessionErrorDismissed
            ? null
            : getErrorMessage(sessionQuery.error, 'Unable to restore your session.'),
        );
      }

      return resolveState(sessionQuery.data);
    })();

    return authError ? { ...resolvedState, error: authError } : resolvedState;
  }, [
    authError,
    isPreviewAuth,
    sessionErrorDismissed,
    sessionQuery.data,
    sessionQuery.error,
    sessionQuery.isError,
    sessionQuery.isPending,
  ]);

  const value = useMemo<AppAuthContext>(
    () => ({
      ...authState,
      login,
      logout,
      refresh,
      clearError,
    }),
    [authState, clearError, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
