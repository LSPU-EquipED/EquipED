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
import { cn } from '@/shared/components/utils';
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
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="fixed inset-x-0 top-0 z-50 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-slate-100 text-slate-700 border border-slate-200">
            <GraduationCap className="size-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
              LSPU SCC
            </p>
            <h1 className="truncate text-sm font-bold text-slate-900">EquipEd Document Evaluation</h1>
          </div>
        </div>

        <div className="hidden w-full max-w-sm items-center md:flex">
          <div className="relative w-full">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              className="h-9 w-full bg-slate-50 border border-slate-200 text-xs pl-9 pr-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm placeholder:text-slate-400"
              placeholder="Search documents"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="flex size-9 items-center justify-center border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
            aria-label="Notifications"
          >
            <Bell className="size-4" aria-hidden="true" />
          </button>

          <div ref={accountMenuRef} className="relative">
            <button
              type="button"
              className="inline-flex h-9 items-center gap-2 border border-slate-200 bg-white hover:bg-slate-50 px-2.5 rounded-sm text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              aria-haspopup="menu"
              aria-expanded={isAccountMenuOpen}
              onClick={() => setIsAccountMenuOpen((value) => !value)}
            >
              <span className="flex size-6 items-center justify-center rounded-full bg-[#1b3b87] text-[10px] font-semibold text-white">
                {initials}
              </span>
              <span className="hidden max-w-40 truncate text-xs sm:inline">
                {user?.displayName ?? 'EquipEd User'}
              </span>
              <ChevronDown className="size-4 text-slate-400" aria-hidden="true" />
            </button>

            {isAccountMenuOpen ? (
              <div
                role="menu"
                className="absolute right-0 top-11 z-50 w-60 rounded-sm border border-slate-200 bg-white p-1.5 text-xs shadow-none"
              >
                <div className="border-b border-slate-200 px-3 py-2">
                  <p className="truncate font-semibold text-slate-800">{user?.displayName ?? 'EquipEd User'}</p>
                  <p className="truncate text-[10px] text-slate-500">
                    {user?.email ?? 'No email available'}
                  </p>
                </div>
                <button
                  type="button"
                  role="menuitem"
                  className="mt-1 flex h-9 w-full items-center gap-2 rounded-sm px-2.5 text-left text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-850"
                >
                  <UserCircle className="size-4" aria-hidden="true" />
                  <span>Profile / Account</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="flex h-9 w-full items-center gap-2 rounded-sm px-2.5 text-left text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-850"
                >
                  <Settings className="size-4" aria-hidden="true" />
                  <span>Settings</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="flex h-9 w-full items-center gap-2 rounded-sm px-2.5 text-left text-red-700 transition-colors hover:bg-red-50"
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
  );
}
