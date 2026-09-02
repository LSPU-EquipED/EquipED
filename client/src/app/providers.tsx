import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from '@tanstack/react-router';
import { appRouter } from './router';
import { appQueryClient } from './runtime';
import { AppLoadingSkeleton } from './components/AppLoadingSkeleton';
import { AuthProvider } from '../features/auth/hooks/AuthProvider';
import { useAuth } from '../features/auth/hooks/useAuth';

function AppBootstrap() {
  const auth = useAuth();

  if (!auth.ready) {
    return <AppLoadingSkeleton />;
  }

  return <RouterProvider router={appRouter} context={{ queryClient: appQueryClient, auth }} />;
}

export function AppProviders() {
  return (
    <QueryClientProvider client={appQueryClient}>
      <AuthProvider>
        <AppBootstrap />
      </AuthProvider>
    </QueryClientProvider>
  );
}
