import { Link, useLocation } from '@tanstack/react-router';
import { useEffect, useRef } from 'react';
import { SidebarSimple, X } from '@phosphor-icons/react';
import { lspuLogoUrl } from '../assets';
import { useIsMobile } from '../hooks/useIsMobile';
import { SHELL_STYLES } from '../theme/tokens';
import { cn } from '../utils';
import type { NavGroup, NavItem } from './navigation.types';
import {
  getAriaCurrent,
  getSidebarInertState,
  isNavigationActive,
} from './navigation.utils';

export interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
  onNavigate?: () => void;
  isMobile?: boolean;
  navGroups: readonly NavGroup[];
  secondaryNavItems?: readonly NavItem[];
  brandSubtitle?: string;
  brandTitle?: string;
  navAriaLabel?: string;
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
    SHELL_STYLES.navItem,
    'group flex items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
    isActive
      ? 'font-semibold text-primary bg-primary-soft border-l-2 border-primary'
      : 'font-medium text-text-muted hover:bg-surface hover:text-text',
    collapsed ? 'md:justify-center md:px-0 max-md:gap-3 max-md:pl-3 max-md:pr-3' : 'gap-3 pl-3 pr-3',
  );
  return (
    <Link
      to={item.to}
      activeOptions={{ exact: item.exact }}
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
  navGroups,
  secondaryNavItems = [],
  brandSubtitle = 'LSPU',
  brandTitle = 'EquipED',
  navAriaLabel = 'Application Navigation',
}: SidebarProps) {
  const isMobileDetected = useIsMobile();
  const isMobile = isMobileProp ?? isMobileDetected;
  const asideRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const pathname = useLocation({ select: (loc) => loc.pathname });

  // Focus management and focus trap for mobile drawer
  useEffect(() => {
    if (!isMobile || !mobileOpen) return;

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

  const { inert, ariaHidden } = getSidebarInertState(isMobile, mobileOpen);
  const handleItemNavigate = () => {
    onNavigate?.();
  };

  return (
    <aside
      ref={asideRef}
      id="app-sidebar"
      aria-label={navAriaLabel}
      {...(inert ? { inert: '' } : {})}
      aria-hidden={ariaHidden ? 'true' : undefined}
      className={cn(
        'fixed bottom-0 left-0 top-0 z-50 flex flex-col transition-all duration-200',
        SHELL_STYLES.sidebar,
        'w-64 max-md:shadow-xl',
        mobileOpen ? 'max-md:translate-x-0' : 'max-md:-translate-x-full',
        'md:translate-x-0',
        collapsed ? 'md:w-[4.5rem]' : 'md:w-64',
      )}
    >
      {/* Brand / Logo */}
      <div
        className={cn(
          'flex h-14 shrink-0 items-center border-b border-border bg-canvas',
          collapsed ? 'md:justify-center md:px-2 max-md:justify-between max-md:px-4' : 'justify-between px-4',
        )}
      >
        <div className="flex items-center gap-3">
          <img src={lspuLogoUrl} alt="LSPU" className="size-9 shrink-0 object-contain" />
          <div className={cn('flex flex-col leading-none', collapsed && 'md:hidden')}>
            <span className="text-[10px] font-medium tracking-[0.08em] text-text-muted">
              {brandSubtitle}
            </span>
            <span className="text-base font-semibold text-text mt-0.5">
              {brandTitle}
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

      {/* Navigation Container */}
      <div className="flex-1 overflow-y-auto py-4">
        <nav aria-label={navAriaLabel} className="grid gap-3 px-3">
          {navGroups.map((group, groupIdx) => (
            <div key={group.id} className="grid gap-1">
              {collapsed && groupIdx > 0 ? (
                <div
                  className="hidden md:block my-1 border-t border-border mx-1"
                  role="separator"
                  aria-hidden="true"
                />
              ) : null}
              <div
                className={cn(
                  'px-3 pt-2 pb-0.5 select-none',
                  SHELL_STYLES.navGroup,
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

        {secondaryNavItems && secondaryNavItems.length > 0 ? (
          <>
            <div className="mx-3 my-3 border-t border-border" role="separator" aria-hidden="true" />
            <nav aria-label="Secondary Navigation" className="grid gap-1 px-3">
              {secondaryNavItems.map((item) => (
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
        ) : null}
      </div>

      {/* Bottom Collapse Toggle (Desktop only) */}
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
            <SidebarSimple className="size-4 shrink-0 rotate-180" aria-hidden="true" />
          ) : (
            <SidebarSimple className="size-4 shrink-0" aria-hidden="true" />
          )}
        </button>
      </div>
    </aside>
  );
}
