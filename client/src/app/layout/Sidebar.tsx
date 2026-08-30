import { Link, useLocation, useNavigate } from '@tanstack/react-router';
import { useEffect, useRef } from 'react';
import {
  PanelLeftClose,
  PanelLeftOpen,
  Upload,
  X,
} from 'lucide-react';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useIsMobile } from '@/shared/hooks/use-mobile';
import { cn } from '@/shared/components/utils';
import {
  adminNavItems,
  facultyNavGroups,
  facultySecondaryNavItems,
  getAriaCurrent,
  getSidebarInertState,
  isNavigationActive,
  type NavItem,
} from './navigation.utils';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
  onNavigate?: () => void;
  isMobile?: boolean;
}

function NavLink({
  item,
  collapsed,
  pathname,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  pathname: string;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const isActive = isNavigationActive(pathname, item.to, item.exact);

  const baseClass = cn(
    'group flex h-10 items-center rounded-sm text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
    isActive
      ? 'font-semibold text-primary bg-primary-soft border-l-2 border-primary'
      : 'font-medium text-text-muted hover:bg-surface-subtle hover:text-text',
    collapsed ? 'md:justify-center md:px-0 max-md:gap-3 max-md:pl-3 max-md:pr-3' : 'gap-3 pl-3 pr-3',
  );
  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      className={baseClass}
      aria-current={getAriaCurrent(isActive)}
      title={collapsed ? item.label : undefined}
      aria-label={collapsed ? item.label : undefined}
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span className={cn('truncate', collapsed && 'md:hidden')}>{item.label}</span>
    </Link>
  );
}

export function Sidebar({
  collapsed,
  onToggle,
  mobileOpen = false,
  onMobileClose,
  onNavigate,
  isMobile: isMobileProp,
}: SidebarProps) {
  const isMobileDetected = useIsMobile();
  const isMobile = isMobileProp ?? isMobileDetected;
  const asideRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const auth = useAuth();
  const { user } = auth;
  const navigate = useNavigate();
  const pathname = useLocation({ select: (loc) => loc.pathname });

  useEffect(() => {
    if (auth.status === 'anonymous') {
      void navigate({ to: '/login' });
    }
  }, [auth.status, navigate]);

  // Focus management and focus trap for mobile drawer
  useEffect(() => {
    if (!isMobile || !mobileOpen) return;

    // Move initial focus into the drawer
    const focusTarget =
      closeButtonRef.current ??
      asideRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
    focusTarget?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onMobileClose?.();
        return;
      }

      if (event.key === 'Tab') {
        const aside = asideRef.current;
        if (!aside) return;

        const focusableElements = aside.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])',
        );

        const focusable = Array.from(focusableElements).filter(
          (el) => el.offsetParent !== null && !el.hasAttribute('disabled'),
        );

        if (focusable.length === 0) return;

        const firstElement = focusable[0];
        const lastElement = focusable[focusable.length - 1];

        if (event.shiftKey) {
          if (document.activeElement === firstElement) {
            event.preventDefault();
            lastElement?.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            event.preventDefault();
            firstElement?.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isMobile, mobileOpen, onMobileClose]);

  const isAdmin = user?.role === 'admin';
  const isUploadActive = isNavigationActive(pathname, '/upload', false);
  const isRubricsActive = isNavigationActive(pathname, '/admin/rubrics', true);

  const { inert, ariaHidden } = getSidebarInertState(isMobile, mobileOpen);

  const handleItemNavigate = () => {
    onNavigate?.();
    onMobileClose?.();
  };

  return (
    <aside
      ref={asideRef}
      id="app-sidebar"
      aria-label="Application Navigation"
      {...(inert ? { inert: '' } : {})}
      aria-hidden={ariaHidden ? 'true' : undefined}
      className={cn(
        'fixed bottom-0 left-0 top-0 z-50 flex flex-col border-r border-border bg-surface-subtle transition-all duration-200',
        'w-72 max-md:shadow-xl',
        mobileOpen ? 'max-md:translate-x-0' : 'max-md:-translate-x-full',
        'md:translate-x-0',
        collapsed ? 'md:w-[5.75rem]' : 'md:w-72',
      )}
    >
      {/* Brand / Logo */}
      <div
        className={cn(
          'flex h-16 shrink-0 items-center border-b border-border bg-surface',
          collapsed ? 'md:justify-center md:px-2 max-md:justify-between max-md:px-4' : 'justify-between px-4',
        )}
      >
        <div className="flex items-center gap-3">
          <img src="/lspu-logo.png" alt="LSPU" className="size-9 shrink-0 object-contain" />
          <div className={cn('flex flex-col leading-none', collapsed && 'md:hidden')}>
            <span className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
              LSPU
            </span>
            <span className="text-base font-bold tracking-tight text-text mt-0.5">
              EquipED
            </span>
          </div>
        </div>

        {/* Mobile Close Button */}
        {onMobileClose ? (
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onMobileClose}
            className="md:hidden flex size-8 items-center justify-center rounded-sm text-text-muted hover:bg-surface hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close navigation menu"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {/* ── Navigation Container ───────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto py-4">
        {!isAdmin ? (
          <>
            {/* Prominent Upload SLM Action */}
            <div className={cn('pb-3', collapsed ? 'md:px-3 md:flex md:justify-center max-md:px-3' : 'px-3')}>
              <Link
                to="/upload"
                onClick={handleItemNavigate}
                aria-current={getAriaCurrent(isUploadActive)}
                className={cn(
                  'flex items-center justify-center rounded-sm text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                  isUploadActive
                    ? 'bg-primary-strong text-primary-foreground shadow-none'
                    : 'bg-primary hover:bg-primary-strong text-primary-foreground shadow-none',
                  collapsed
                    ? 'md:size-10 max-md:h-10 max-md:w-full max-md:gap-2 max-md:px-3 max-md:tracking-wide max-md:uppercase max-md:text-xs'
                    : 'h-10 w-full gap-2 px-3 tracking-wide uppercase text-xs',
                )}
                title={collapsed ? 'Upload SLM' : undefined}
                aria-label="Upload SLM"
              >
                <Upload className="size-4 shrink-0" aria-hidden="true" />
                <span className={cn(collapsed && 'md:hidden')}>Upload SLM</span>
              </Link>
            </div>

            {/* Grouped Faculty Navigation */}
            <nav aria-label="Faculty Navigation" className="grid gap-3 px-3">
              {facultyNavGroups.map((group, groupIdx) => (
                <div key={group.id} className="grid gap-1">
                  {collapsed ? (
                    groupIdx > 0 ? (
                      <div
                        className="hidden md:block my-1 border-t border-border mx-1"
                        role="separator"
                        aria-hidden="true"
                      />
                    ) : null
                  ) : null}
                  <div
                    className={cn(
                      'px-3 pt-2 pb-0.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted select-none',
                      collapsed && 'md:hidden',
                    )}
                  >
                    {group.label}
                  </div>
                  {group.items.map((item) => (
                    <NavLink
                      key={item.to}
                      item={item}
                      collapsed={collapsed}
                      pathname={pathname}
                      onNavigate={handleItemNavigate}
                    />
                  ))}
                </div>
              ))}
            </nav>

            <div className="mx-3 my-3 border-t border-border" role="separator" aria-hidden="true" />

            {/* Secondary Faculty Navigation */}
            <nav aria-label="Secondary Navigation" className="grid gap-1 px-3">
              {facultySecondaryNavItems.map((item) => (
                <NavLink
                  key={item.to}
                  item={item}
                  collapsed={collapsed}
                  pathname={pathname}
                  onNavigate={handleItemNavigate}
                />
              ))}
            </nav>
          </>
        ) : (
          <>
            {/* Admin Navigation */}
            <nav aria-label="Admin Navigation" className="grid gap-1 px-3">
              {adminNavItems.map((item) => (
                <NavLink
                  key={item.to}
                  item={item}
                  collapsed={collapsed}
                  pathname={pathname}
                  onNavigate={handleItemNavigate}
                />
              ))}
            </nav>

            <div className="mx-3 my-4 border-t border-border" role="separator" aria-hidden="true" />

            <nav aria-label="Secondary" className="grid gap-1 px-3">
              <Link
                to="/admin/rubrics"
                onClick={handleItemNavigate}
                aria-current={getAriaCurrent(isRubricsActive)}
                className={cn(
                  'group flex h-10 items-center rounded-sm text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isRubricsActive
                    ? 'font-semibold text-primary bg-primary-soft border-l-2 border-primary'
                    : 'font-medium text-text-muted hover:bg-surface-subtle hover:text-text',
                  collapsed
                    ? 'md:justify-center md:px-0 max-md:gap-3 max-md:pl-3 max-md:pr-3'
                    : 'gap-3 pl-3 pr-3',
                )}
                title={collapsed ? 'Rubrics' : undefined}
                aria-label={collapsed ? 'Rubrics' : undefined}
              >
                <Upload className="size-4 shrink-0" aria-hidden="true" />
                <span className={cn('truncate', collapsed && 'md:hidden')}>Rubrics</span>
              </Link>
            </nav>
          </>
        )}
      </div>

      {/* ── Bottom Collapse Toggle (Desktop only) ───────────────────────── */}
      <div
        className={cn(
          'hidden md:flex h-12 shrink-0 items-center px-3 border-t border-border bg-surface mt-auto',
          collapsed ? 'justify-center' : 'justify-end',
        )}
      >
        <button
          type="button"
          onClick={onToggle}
          className="flex size-9 items-center justify-center rounded-sm text-text-muted transition-colors hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-4 shrink-0" aria-hidden="true" />
          ) : (
            <PanelLeftClose className="size-4 shrink-0" aria-hidden="true" />
          )}
        </button>
      </div>
    </aside>
  );
}
