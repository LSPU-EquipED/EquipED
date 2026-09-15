import { QueryClient } from '@tanstack/react-query';
import type { AppAuthContext } from '../features/auth/types';

export type AppRouterContext = {
  queryClient: QueryClient;
  auth: AppAuthContext;
};

export const appQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export const appRouterContext: AppRouterContext = {
  queryClient: appQueryClient,
  auth: {
    status: 'anonymous',
    source: 'provisional',
    ready: false,
    error: null,
    user: null,
    login: async () => undefined,
    logout: async () => undefined,
    refresh: async () => undefined,
    clearError: () => undefined,
  },
};
