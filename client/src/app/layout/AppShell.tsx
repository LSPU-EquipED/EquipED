import { Outlet } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import {
  Bell,
  ChevronDown,
  GraduationCap,
  LogOut,
  Search,
  Settings,
  UserCircle,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { cn } from '@/shared/components/utils';
import { TooltipProvider } from '@/shared/components/ui/tooltip';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { Sidebar } from './Sidebar';

export function AppShell() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const { logout, user } = useAuth();
  const initials =
    user?.displayName
      ?.split(/\s+/)
      .filter(Boolean)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('')
      .slice(0, 2) || 'EA';

  useEffect(() => {
    if (!isAccountMenuOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!accountMenuRef.current?.contains(event.target as Node)) {
        setIsAccountMenuOpen(false);
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
    };
  }, [isAccountMenuOpen]);

  const handleLogout = async () => {
    setIsAccountMenuOpen(false);
    await logout();
  };

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background text-foreground">
        <header className="fixed inset-x-0 top-0 z-50 flex h-16 items-center justify-between border-b bg-card/95 px-6 backdrop-blur">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-lg bg-muted text-foreground">
              <GraduationCap className="size-5" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                LSPU SCC
              </p>
              <h1 className="truncate text-base font-semibold">EquipEd Document Evaluation</h1>
            </div>
          </div>

          <div className="hidden w-full max-w-sm items-center md:flex">
            <div className="relative w-full">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="h-9 rounded-lg bg-muted/40 pl-9" placeholder="Search documents" />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon-lg" aria-label="Notifications">
              <Bell className="size-4" aria-hidden="true" />
            </Button>

            <div ref={accountMenuRef} className="relative">
              <Button
                type="button"
                variant="outline"
                className="h-9 gap-2 px-2.5"
                aria-haspopup="menu"
                aria-expanded={isAccountMenuOpen}
                onClick={() => setIsAccountMenuOpen((value) => !value)}
              >
                <span className="flex size-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  {initials}
                </span>
                <span className="hidden max-w-40 truncate text-sm sm:inline">
                  {user?.displayName ?? 'EquipEd User'}
                </span>
                <ChevronDown className="size-4 text-muted-foreground" aria-hidden="true" />
              </Button>

              {isAccountMenuOpen ? (
                <div
                  role="menu"
                  className="absolute right-0 top-11 z-50 w-60 rounded-lg border bg-card p-1.5 text-sm shadow-lg"
                >
                  <div className="border-b px-3 py-2">
                    <p className="truncate font-semibold">{user?.displayName ?? 'EquipEd User'}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {user?.email ?? 'No email available'}
                    </p>
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    className="mt-1 flex h-9 w-full items-center gap-2 rounded-md px-2.5 text-left text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    <UserCircle className="size-4" aria-hidden="true" />
                    <span>Profile / Account</span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="flex h-9 w-full items-center gap-2 rounded-md px-2.5 text-left text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    <Settings className="size-4" aria-hidden="true" />
                    <span>Settings</span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="flex h-9 w-full items-center gap-2 rounded-md px-2.5 text-left text-destructive transition-colors hover:bg-destructive/10"
                    onClick={() => {
                      void handleLogout();
                    }}
                  >
                    <LogOut className="size-4" aria-hidden="true" />
                    <span>Sign Out</span>
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <Sidebar
          collapsed={isSidebarCollapsed}
          onToggle={() => setIsSidebarCollapsed((value) => !value)}
        />

        <div
          className={cn(
            'min-h-screen min-w-0 pt-16 transition-[padding] duration-200',
            isSidebarCollapsed ? 'pl-[5.75rem]' : 'pl-72 max-md:pl-[5.75rem]',
          )}
        >
          <main className="min-w-0 px-6 py-7">
            <Outlet />
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
