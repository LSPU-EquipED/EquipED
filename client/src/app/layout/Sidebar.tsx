import { Link } from '@tanstack/react-router';
import { useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import {
  BookOpen,
  ChevronDown,
  ChevronsUpDown,
  FilePlus2,
  FileUp,
  FolderOpen,
  GraduationCap,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Shield,
  Upload,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { cn } from '@/shared/components/utils';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  exact: boolean;
};

const workspaceNavItems: readonly NavItem[] = [
  { to: '/dashboard', label: 'Documents', icon: FolderOpen, exact: true },
  { to: '/upload', label: 'Upload', icon: FilePlus2, exact: true },
] as const;

const adminNavItems: readonly NavItem[] = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/admin/users', label: 'Users', icon: Users, exact: true },
  { to: '/admin/ingest', label: 'Ingest', icon: FileUp, exact: true },
  { to: '/matrix', label: 'Monitoring Matrix', icon: Shield, exact: true },
  { to: '/admin/prompts', label: 'Prompts', icon: Settings, exact: false },
  { to: '/admin/preferences', label: 'Logs', icon: BookOpen, exact: true },
] as const;

const resourceItems = [
  { label: 'Guidelines', icon: GraduationCap },
] as const;

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const asideWidth = collapsed ? 'w-[5.75rem]' : 'w-72 max-md:w-[5.75rem]';
  const auth = useAuth();
  const { user } = auth;
  const navigate = useNavigate();

  useEffect(() => {
    if (auth.status === 'anonymous') {
      void navigate({ to: '/login' });
    }
  }, [auth.status, navigate]);

  const isAdmin = user?.role === 'admin';

  return (
    <aside
      className={cn(
        'fixed bottom-0 left-0 top-16 z-40 flex flex-col overflow-hidden border-r bg-sidebar text-sidebar-foreground transition-[width] duration-200',
        asideWidth
      )}
    >
      <nav aria-label="Primary" className="grid gap-1 px-3 py-4">
        {!isAdmin && (
          <>
            {!collapsed && (
              <div className="px-3 pb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Workspace
              </div>
            )}
            {workspaceNavItems.map((item) => {
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
        </>
        )}

        {isAdmin && (
          <>
            {!collapsed && (
              <div className="mt-6 px-3 pb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                System Management
              </div>
            )}
            {adminNavItems.map((item) => {
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
          </>
        )}
      </nav>

      <div className="mt-7 grid gap-1 px-3">
        {!collapsed && <div className="px-3 pb-2 text-xs font-medium text-muted-foreground">Resources</div>}
        {isAdmin && (
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
            <Upload className="size-4 shrink-0" aria-hidden="true" />
            {!collapsed && <span className="truncate">Rubrics</span>}
          </Link>
        )}
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
          onClick={onToggle}
          className={cn(
            'flex h-10 w-full items-center rounded-lg text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
            collapsed ? 'justify-center px-0' : 'gap-3 px-3'
          )}
          title={collapsed ? 'Expand sidebar' : undefined}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-4 shrink-0" aria-hidden="true" />
          ) : (
            <>
              <PanelLeftClose className="size-4 shrink-0" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-left">Collapse sidebar</span>
              <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
