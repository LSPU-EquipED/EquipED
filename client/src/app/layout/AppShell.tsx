import { Outlet, useMatches } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import { LogOut } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { Sidebar } from './Sidebar';

function getRouteTitle(routeId?: string): string {
  if (!routeId) return 'EquipED';

  if (routeId.includes('/dashboard')) return 'Documents';
  if (routeId.includes('/upload')) return 'Upload Document';
  if (routeId.includes('/evaluations/$id/report')) return 'Evaluation Report';
  if (routeId.includes('/evaluations/$id')) return 'Scorecard';
  if (routeId.includes('/evaluations')) return 'Evaluations';
  if (routeId.includes('/evaluation-map')) return 'Knowledge Map';
  if (routeId.includes('/documents/') && routeId.includes('/evaluation'))
    return 'Evaluation Interface';
  if (routeId.includes('/matrix')) return 'Monitoring Matrix';
  if (routeId.includes('/alignment')) return 'Curriculum Alignment';
  if (routeId.includes('/admin/users')) return 'User Management';
  if (routeId.includes('/admin/ingest')) return 'Reference Ingestion';
  if (routeId.includes('/admin/references')) return 'Reference Library';
  if (routeId.includes('/admin/prompts')) return 'Agent Prompts';
  if (routeId.includes('/admin/preferences')) return 'Preference Logs';
  if (routeId.includes('/admin/rubrics')) return 'Rubric Editor';
  if (routeId.includes('/admin')) return 'Admin Dashboard';

  return 'EquipED';
}

export function AppShell() {
  const matches = useMatches();
  const currentMatch = matches[matches.length - 1];
  const routeId = currentMatch?.routeId;

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
    <div className="min-h-screen bg-white text-slate-800">
      <header
        className={cn(
          'fixed right-0 top-0 z-40 flex h-16 items-center border-b border-slate-200 bg-white px-6 transition-[left] duration-200',
          isSidebarCollapsed ? 'left-[5.75rem]' : 'left-72 max-md:left-[5.75rem]',
        )}
      >
        <div className="flex flex-1 items-center gap-3">
          <span className="text-base font-bold text-slate-900">{getRouteTitle(routeId)}</span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div ref={accountMenuRef} className="relative">
            <button
              type="button"
              className="flex size-8 items-center justify-center rounded-full bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#1b3b87] focus:ring-offset-2"
              aria-haspopup="menu"
              aria-expanded={isAccountMenuOpen}
              onClick={() => setIsAccountMenuOpen((value) => !value)}
            >
              {initials}
            </button>

            {isAccountMenuOpen ? (
              <div
                role="menu"
                className="absolute right-0 top-11 z-50 w-60 rounded-sm border border-slate-200 bg-white p-1.5 text-xs shadow-none"
              >
                <div className="border-b border-slate-200 px-3 py-2">
                  <p className="truncate font-semibold text-slate-800">
                    {user?.displayName ?? 'EquipEd User'}
                  </p>
                  <p className="truncate text-[10px] text-slate-500">
                    {user?.email ?? 'No email available'}
                  </p>
                </div>
                <button
                  type="button"
                  role="menuitem"
                  className="flex h-9 w-full items-center gap-2 rounded-sm px-2.5 text-left text-[#b91c1c] transition-colors hover:bg-[#b91c1c]/10"
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
        <main className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
