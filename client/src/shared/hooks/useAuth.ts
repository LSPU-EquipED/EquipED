import { useCallback, useMemo } from 'react';
import { useLocalStorage } from './useLocalStorage';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role?: string;
}

interface AuthSession {
  token: string;
  user: AuthUser;
}

export function useAuth(storageKey = 'equiped.auth.session') {
  const [session, setSession] = useLocalStorage<AuthSession | null>(storageKey, null);

  const login = useCallback(
    (nextSession: AuthSession) => {
      setSession(nextSession);
    },
    [setSession],
  );

  const logout = useCallback(() => {
    setSession(null);
  }, [setSession]);

  const updateUser = useCallback(
    (userPatch: Partial<AuthUser>) => {
      setSession((current) => {
        if (!current) {
          return current;
        }

        return {
          ...current,
          user: {
            ...current.user,
            ...userPatch,
          },
        };
      });
    },
    [setSession],
  );

  const isAuthenticated = Boolean(session?.token);

  return useMemo(
    () => ({
      session,
      user: session?.user ?? null,
      token: session?.token ?? null,
      isAuthenticated,
      login,
      logout,
      updateUser,
    }),
    [isAuthenticated, login, logout, session, updateUser],
  );
}

export type { AuthSession };
