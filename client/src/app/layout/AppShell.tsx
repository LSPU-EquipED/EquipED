import { Outlet, useLocation, useMatches } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import { LogOut, Menu } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useIsMobile } from '@/shared/hooks/use-mobile';
import { Sidebar } from './Sidebar';
import { getRouteTitle, getSidebarLayoutClasses } from './navigation.utils';

export function AppShell() {
  const matches = useMatches();
  const currentMatch = matches[matches.length - 1];
  const routeId = currentMatch?.routeId;
  const pathname = useLocation({ select: (loc) => loc.pathname });
  const isMobile = useIsMobile();

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);

  const mobileMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const accountTriggerRef = useRef<HTMLButtonElement>(null);
  const accountMenuRef = useRef<HTMLDivElement>(null);

  const { logout, user } = useAuth();
  const initials =
    user?.displayName
      ?.split(/\s+/)
      .filter(Boolean)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('')
      .slice(0, 2) || 'EA';

  const closeMobileMenu = (restoreFocus = true) => {
    setIsMobileMenuOpen(false);
    if (restoreFocus) {
      mobileMenuTriggerRef.current?.focus();
    }
  };

  // Automatically close mobile menu upon route changes
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  // Account menu outside-click and Escape key handler
  useEffect(() => {
    if (!isAccountMenuOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!accountMenuRef.current?.contains(event.target as Node)) {
        setIsAccountMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setIsAccountMenuOpen(false);
        accountTriggerRef.current?.focus();
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isAccountMenuOpen]);

  const handleLogout = async () => {
    setIsAccountMenuOpen(false);
    await logout();
  };

  const layoutClasses = getSidebarLayoutClasses(isSidebarCollapsed);

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <header
        className={cn(
          'fixed right-0 top-0 z-40 flex h-16 items-center border-b border-slate-200 bg-white px-4 sm:px-6 transition-[left] duration-200',
          layoutClasses.headerLeft,
        )}
      >
        <div className="flex flex-1 items-center gap-3">
          {/* Mobile menu hamburger toggle */}
          <button
            type="button"
            ref={mobileMenuTriggerRef}
            onClick={() => setIsMobileMenuOpen(true)}
            className="md:hidden -ml-1 mr-1 flex size-9 items-center justify-center rounded-sm text-slate-700 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
            aria-label="Open navigation menu"
            aria-expanded={isMobileMenuOpen}
            aria-controls="app-sidebar"
          >
            <Menu className="size-5" aria-hidden="true" />
          </button>

          <span className="text-base font-bold text-slate-900">
            {getRouteTitle(routeId, user?.role)}
          </span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div ref={accountMenuRef} className="relative">
            <button
              type="button"
              ref={accountTriggerRef}
              className="flex size-8 items-center justify-center rounded-full bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#1b3b87] focus:ring-offset-2"
              aria-haspopup="menu"
              aria-expanded={isAccountMenuOpen}
              aria-label={`User account menu for ${user?.displayName ?? user?.email ?? 'faculty'}`}
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

      {/* Mobile Drawer Backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs md:hidden"
          aria-hidden="true"
          onClick={() => closeMobileMenu(true)}
        />
      )}

      <Sidebar
        collapsed={isSidebarCollapsed}
        onToggle={() => setIsSidebarCollapsed((value) => !value)}
        mobileOpen={isMobileMenuOpen}
        onMobileClose={() => closeMobileMenu(true)}
        onNavigate={() => closeMobileMenu(true)}
        isMobile={isMobile}
      />

      <div
        className={cn(
          'min-h-screen min-w-0 pt-16 transition-[padding] duration-200',
          layoutClasses.mainPadding,
        )}
      >
        <main className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
