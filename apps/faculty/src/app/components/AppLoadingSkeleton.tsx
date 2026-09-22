import { Skeleton } from '@equiped/ui';

export function AppLoadingSkeleton() {
  return (
    <div
      className="min-h-screen bg-canvas text-text"
      role="status"
      aria-label="Loading EquipED workspace"
      aria-busy="true"
    >
      {/* Topbar Skeleton mirroring AppShell SHELL_STYLES.topbar */}
      <header className="fixed right-0 top-0 z-40 flex h-14 items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur-xs transition-[left] sm:px-6 left-0 md:left-64">
        <div className="flex items-center gap-2.5 min-w-0">
          <Skeleton className="size-4 shrink-0 rounded-xs" />
          <span className="text-text-muted/40 text-xs">/</span>
          <Skeleton className="h-3.5 w-28" />
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="size-8 rounded-sm" />
        </div>
      </header>

      {/* Sidebar Skeleton mirroring Sidebar.tsx */}
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-64 flex-col border-r border-border bg-surface p-4 md:flex">
        <div className="flex items-center gap-3 border-b border-border pb-4 px-1">
          <Skeleton className="size-8 rounded-sm shrink-0" />
          <div className="flex-1 space-y-1.5 min-w-0">
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="h-2.5 w-16" />
          </div>
        </div>
        <div className="mt-5 space-y-2 px-1">
          <Skeleton className="h-2 w-14 mb-3" />
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="flex items-center gap-3 py-1.5 px-1">
              <Skeleton className="size-4 shrink-0 rounded-xs" />
              <Skeleton className="h-3.5 flex-1" />
            </div>
          ))}
        </div>
        <div className="mt-auto border-t border-border pt-4 px-1">
          <div className="flex items-center gap-3">
            <Skeleton className="size-7 rounded-sm shrink-0" />
            <div className="flex-1 space-y-1 min-w-0">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-2.5 w-14" />
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area mirroring mainPadding and layout */}
      <div className="min-h-screen min-w-0 bg-canvas pt-14 md:pl-64">
        <main className="min-w-0 p-5 sm:p-7 space-y-6">
          {/* Page header skeleton */}
          <div className="space-y-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-7 w-64 max-w-full" />
            <Skeleton className="h-3.5 w-96 max-w-full" />
          </div>

          {/* Metric cards strip skeleton */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="space-y-3 rounded-sm border border-border bg-surface p-4">
                <Skeleton className="size-8 rounded-sm" />
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-6 w-16" />
              </div>
            ))}
          </div>

          {/* Content table/ledger skeleton */}
          <div className="rounded-sm border border-border bg-surface p-5 space-y-4">
            <div className="flex items-center justify-between gap-4 border-b border-border pb-4">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-8 w-28" />
            </div>
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="flex items-center gap-4 py-2 border-b border-border/50 last:border-0">
                <Skeleton className="size-4 shrink-0 rounded-xs" />
                <Skeleton className="h-4 w-1/4" />
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-4 w-1/6 ml-auto" />
              </div>
            ))}
          </div>
        </main>
      </div>
      <span className="sr-only">Restoring your secure workspace.</span>
    </div>
  );
}
