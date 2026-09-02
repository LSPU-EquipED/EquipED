import { Skeleton } from '@/shared/components/Skeleton';

export function AppLoadingSkeleton() {
  return (
    <div
      className="min-h-screen bg-canvas px-4 py-6 sm:px-6 lg:px-8"
      role="status"
      aria-label="Loading EquipED workspace"
      aria-busy="true"
    >
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-[108rem] overflow-hidden rounded-md border border-border bg-surface">
        <aside className="hidden w-64 shrink-0 border-r border-border bg-surface-subtle p-5 lg:flex lg:flex-col">
          <div className="flex items-center gap-3 border-b border-border pb-5">
            <Skeleton className="size-10 rounded-sm" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-2.5 w-16" />
            </div>
          </div>
          <div className="mt-8 space-y-3">
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className="h-9 w-full" />
            ))}
          </div>
          <Skeleton className="mt-auto h-9 w-full" />
        </aside>

        <main className="min-w-0 flex-1">
          <div className="flex h-16 items-center justify-between border-b border-border px-5 sm:px-8">
            <div className="space-y-2">
              <Skeleton className="h-2.5 w-20" />
              <Skeleton className="h-4 w-40" />
            </div>
            <Skeleton className="size-9 rounded-full" />
          </div>
          <div className="space-y-6 p-5 sm:p-8">
            <div className="space-y-3">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-8 w-64 max-w-full" />
              <Skeleton className="h-3 w-80 max-w-full" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="space-y-4 border border-border p-5">
                  <Skeleton className="size-9" />
                  <Skeleton className="h-2.5 w-24" />
                  <Skeleton className="h-7 w-16" />
                </div>
              ))}
            </div>
            <div className="space-y-4 border border-border p-5">
              <div className="flex items-center justify-between gap-4">
                <Skeleton className="h-4 w-44" />
                <Skeleton className="h-8 w-24" />
              </div>
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          </div>
        </main>
      </div>
      <span className="sr-only">Restoring your secure workspace.</span>
    </div>
  );
}
