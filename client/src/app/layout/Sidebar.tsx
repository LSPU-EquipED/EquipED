import { Link } from '@tanstack/react-router';
import { useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import {
  Archive,
  BookOpen,
  ChevronDown,
  ChevronsUpDown,
  ClipboardList,
  FilePlus2,
  FolderOpen,
  GraduationCap,
  LayoutDashboard,
  Library,
  LogOut,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import { useAuth } from '@/features/auth/hooks/useAuth';
import type { UserRole } from '@/features/auth/types';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/components/utils';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

type NavItem = {
  to:
    | '/dashboard'
    | '/upload'
    | '/evaluations'
    | '/evaluation-interface'
    | '/matrix'
    | '/admin/prompts'
    | '/admin/rubrics';
  label: string;
  icon: LucideIcon;
  exact: boolean;
  allowedRoles?: readonly UserRole[];
};

const navItems: readonly NavItem[] = [
  { to: '/dashboard', label: 'Documents', icon: FolderOpen, exact: true },
  { to: '/upload', label: 'Upload', icon: FilePlus2, exact: true },
  { to: '/evaluations', label: 'Reviews', icon: Archive, exact: false },
  { to: '/matrix', label: 'Matrix', icon: LayoutDashboard, exact: true, allowedRoles: ['admin'] },
  { to: '/admin/prompts', label: 'Admin', icon: ShieldCheck, exact: false, allowedRoles: ['admin'] },
] as const;

const resourceItems = [
  { label: 'Guidelines', icon: GraduationCap },
  { label: 'Settings', icon: Settings },
] as const;

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const asideWidth = collapsed ? 'w-[5.75rem]' : 'w-72 max-md:w-[5.75rem]';
  const auth = useAuth();
  const { logout, user } = auth;
  const navigate = useNavigate();
  const visibleNavItems = navItems.filter(
    (item) => !item.allowedRoles || (user && item.allowedRoles.includes(user.role)),
  );
  const initials = user?.displayName
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
    .slice(0, 2) || 'EA';

  const handleLogout = async () => {
    await logout();
  };

  useEffect(() => {
    if (auth.status === 'anonymous') {
      void navigate({ to: '/login' });
    }
  }, [auth.status, navigate]);

  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-40 flex flex-col overflow-hidden border-r bg-sidebar text-sidebar-foreground transition-[width] duration-200',
        asideWidth
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex h-20 items-center gap-3 px-4 text-left transition-colors hover:bg-sidebar-accent"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-foreground text-background shadow-sm">
          <Library className="size-5" aria-hidden="true" />
        </div>

        {!collapsed && (
          <>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold">EquipEd</div>
              <div className="truncate text-sm text-muted-foreground">LSPU SCC</div>
            </div>
            <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          </>
        )}
      </button>

      <nav aria-label="Primary" className="mt-3 grid gap-1 px-3">
        {!collapsed && <div className="px-3 pb-2 text-xs font-medium text-muted-foreground">Workspace</div>}
        {visibleNavItems.map((item) => {
          const Icon = item.icon;
          const baseClass = cn(
            'group flex h-10 items-center rounded-lg text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
            collapsed ? 'justify-center px-0' : 'gap-3 px-3'
          );

          return (
            <Link
              key={item.to}
              to={item.to}
              activeOptions={{ exact: item.exact }}
              className={baseClass}
              activeProps={{
                className: cn(baseClass, 'bg-sidebar-accent text-foreground'),
              }}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="size-4 shrink-0" aria-hidden="true" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
        {user?.role === 'admin' && (
          <Link
            to="/admin/rubrics"
            activeOptions={{ exact: true }}
            className={cn(
              'group flex h-10 items-center rounded-lg text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
              collapsed ? 'justify-center px-0' : 'gap-3 px-3'
            )}
            activeProps={{
              className: cn(
                'group flex h-10 items-center rounded-lg text-sm font-medium transition-colors',
                collapsed ? 'justify-center px-0' : 'gap-3 px-3',
                'bg-sidebar-accent text-foreground'
              ),
            }}
            title={collapsed ? 'Rubrics' : undefined}
          >
            <BookOpen className="size-4 shrink-0" aria-hidden="true" />
            {!collapsed && <span className="truncate">Rubrics</span>}
          </Link>
        )}
      </nav>

      <div className="mt-7 grid gap-1 px-3">
        {!collapsed && <div className="px-3 pb-2 text-xs font-medium text-muted-foreground">Temporary</div>}
        <Link
          to="/evaluation-interface"
          activeOptions={{ exact: true }}
          className={cn(
            'group flex h-10 items-center rounded-lg text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
            collapsed ? 'justify-center px-0' : 'gap-3 px-3'
          )}
          activeProps={{
            className: cn(
              'group flex h-10 items-center rounded-lg text-sm font-medium transition-colors',
              collapsed ? 'justify-center px-0' : 'gap-3 px-3',
              'bg-sidebar-accent text-foreground'
            ),
          }}
          title={collapsed ? 'Evaluation Interface' : undefined}
        >
          <ClipboardList className="size-4 shrink-0" aria-hidden="true" />
          {!collapsed && <span className="truncate">Evaluation Interface</span>}
        </Link>
      </div>

      <div className="mt-7 grid gap-1 px-3">
        {!collapsed && <div className="px-3 pb-2 text-xs font-medium text-muted-foreground">Resources</div>}
        {resourceItems.map((item) => {
          const Icon = item.icon;

          return (
            <button
              key={item.label}
              type="button"
              className={cn(
                'flex h-10 items-center rounded-lg text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                collapsed ? 'justify-center px-0' : 'gap-3 px-3'
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="size-4 shrink-0" aria-hidden="true" />
              {!collapsed && (
                <>
                  <span className="min-w-0 flex-1 truncate text-left">{item.label}</span>
                  <ChevronDown className="size-4 text-muted-foreground" aria-hidden="true" />
                </>
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-auto border-t p-3">
        <button
          type="button"
          className={cn(
            'flex w-full items-center rounded-lg text-left transition-colors hover:bg-sidebar-accent',
            collapsed ? 'justify-center p-2' : 'gap-3 p-2'
          )}
          title={collapsed ? user?.displayName ?? 'EquipEd User' : undefined}
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold text-foreground">
            {initials}
          </span>
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">{user?.displayName ?? 'EquipEd User'}</span>
                <span className="block truncate text-xs text-muted-foreground">{user?.email ?? 'No email available'}</span>
              </span>
              <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            </>
          )}
        </button>

        <Button
          type="button"
          variant="ghost"
          className={cn('mt-2 w-full justify-start gap-2', collapsed && 'justify-center px-0')}
          onClick={() => {
            void handleLogout();
          }}
          title={collapsed ? 'Sign out' : undefined}
        >
          <LogOut className="size-4" aria-hidden="true" />
          {!collapsed && <span>Sign out</span>}
        </Button>
      </div>
    </aside>
  );
}
