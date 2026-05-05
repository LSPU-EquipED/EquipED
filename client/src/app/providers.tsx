import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from '@tanstack/react-router';
import { appRouter } from './router';
import { appQueryClient } from './runtime';

export function AppProviders() {
  return (
    <QueryClientProvider client={appQueryClient}>
      <RouterProvider router={appRouter} />
    </QueryClientProvider>
  );
}
