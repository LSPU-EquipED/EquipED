import { Outlet } from '@tanstack/react-router';
import { useState } from 'react';
import { Bell, ChevronDown, GraduationCap, Search } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { cn } from '@/shared/components/utils';
import { Sidebar } from './Sidebar';

export function AppShell() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Sidebar collapsed={isSidebarCollapsed} onToggle={() => setIsSidebarCollapsed((value) => !value)} />

      <div
        className={cn(
          'min-h-screen min-w-0 transition-[padding] duration-200',
          isSidebarCollapsed ? 'pl-[5.75rem]' : 'pl-72 max-md:pl-[5.75rem]'
        )}
      >
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-card/95 px-6 backdrop-blur">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-lg bg-muted text-foreground">
              <GraduationCap className="size-5" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">LSPU SCC</p>
              <h1 className="truncate text-base font-semibold">EquipEd Document Evaluation</h1>
            </div>
          </div>

          <div className="hidden w-full max-w-sm items-center md:flex">
            <div className="relative w-full">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="h-9 rounded-lg bg-muted/40 pl-9" placeholder="Search documents or reports" />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon-lg" aria-label="Notifications">
              <Bell className="size-4" aria-hidden="true" />
            </Button>
            <Button variant="outline" className="h-9 gap-2 px-2.5">
              <span className="flex size-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                MA
              </span>
              <span className="hidden text-sm sm:inline">Marc Alberto</span>
              <ChevronDown className="size-4 text-muted-foreground" aria-hidden="true" />
            </Button>
          </div>
        </header>

        <main className="min-w-0 px-6 py-7">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
