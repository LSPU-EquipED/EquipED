import { Link, Outlet, useLocation, useMatches } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import { CaretRight, House, List, SignOut } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useIsMobile } from '@/shared/hooks/use-mobile';
import { Sidebar } from './Sidebar';
import { getBreadcrumbs, getSidebarLayoutClasses } from './navigation.utils';
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
  const breadcrumbs = getBreadcrumbs(pathname, user?.role);

  return (
    <div className="min-h-screen bg-canvas text-text">
      <header
        className={cn(
          'fixed right-0 top-0 z-40 flex h-16 items-center border-b border-border bg-surface px-4 sm:px-6 transition-[left] duration-200',
          layoutClasses.headerLeft,
        )}
      >
        <div className="flex flex-1 items-center gap-3 min-w-0">
          {/* Mobile menu hamburger toggle */}
          <button
            type="button"
            ref={mobileMenuTriggerRef}
            onClick={() => setIsMobileMenuOpen(true)}
            className="md:hidden -ml-1 mr-1 flex size-9 items-center justify-center rounded-sm text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring shrink-0"
            aria-label="Open navigation menu"
            aria-expanded={isMobileMenuOpen}
            aria-controls="app-sidebar"
          >
            <List className="size-5" aria-hidden="true" />
          </button>

          {/* Dynamic Breadcrumbs */}
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs sm:text-sm text-text-muted min-w-0 overflow-hidden">
            <Link
              to={user?.role === 'admin' ? '/admin' : '/dashboard'}
              className="flex items-center text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-xs shrink-0"
              title={user?.role === 'admin' ? 'Admin Dashboard' : 'Faculty Workspace'}
              aria-label={user?.role === 'admin' ? 'Admin Dashboard' : 'Faculty Workspace'}
            >
              <House className="size-4 shrink-0" aria-hidden="true" />
            </Link>
            {breadcrumbs.map((crumb, idx) => {
              const isLast = idx === breadcrumbs.length - 1;
              return (
                <div key={`${crumb.label}-${idx}`} className="flex items-center gap-1.5 min-w-0">
                  <CaretRight className="size-3 shrink-0 text-text-muted/60" aria-hidden="true" />
                  {crumb.to && !isLast ? (
                    <Link
                      to={crumb.to}
                      className="truncate font-medium text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-xs"
                    >
                      {crumb.label}
                    </Link>
                  ) : (
                    <span
                      className={cn(
                        'truncate',
                        isLast ? 'font-semibold text-text' : 'font-medium text-text-muted',
                      )}
                    >
                      {crumb.label}
                    </span>
                  )}
                </div>
              );
            })}
          </nav>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div ref={accountMenuRef} className="relative">
            <button
              type="button"
              ref={accountTriggerRef}
              className="flex size-8 items-center justify-center rounded-full bg-primary hover:bg-primary-strong text-xs font-semibold text-primary-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
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
                className="absolute right-0 top-11 z-50 w-60 rounded-sm border border-border bg-surface p-1.5 text-xs shadow-sm"
              >
                <div className="border-b border-border px-3 py-2">
                  <p className="truncate font-semibold text-text">
                    {user?.displayName ?? 'EquipEd User'}
                  </p>
                  <p className="truncate text-[11px] text-text-muted">
                    {user?.email ?? 'No email available'}
                  </p>
                </div>
                <button
                  type="button"
                  role="menuitem"
                  className="flex h-9 w-full items-center gap-2 rounded-sm px-2.5 text-left text-destructive transition-colors hover:bg-destructive-soft"
                  onClick={() => {
                    void handleLogout();
                  }}
                >
                  <SignOut className="size-4" aria-hidden="true" />
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
