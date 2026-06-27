import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from '@tanstack/react-router';
import { appRouter } from './router';
import { appQueryClient } from './runtime';
import { AuthProvider } from '../features/auth/hooks/AuthProvider';
import { useAuth } from '../features/auth/hooks/useAuth';

function AppBootstrap() {
  const auth = useAuth();

  if (!auth.ready) {
    return (
      <div className="grid min-h-screen place-items-center bg-white px-6 text-center text-slate-900">
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">EquipEd</p>
          <h1 className="text-xl font-semibold">Checking session…</h1>
          <p className="text-sm text-slate-500">
            Restoring your workspace before loading the dashboard.
          </p>
        </div>
      </div>
    );
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
