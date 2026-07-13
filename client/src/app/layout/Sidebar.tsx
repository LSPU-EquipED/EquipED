import { Link } from '@tanstack/react-router';
import { useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import {
  BookOpen,
  ClipboardList,
  FilePlus2,
  FileUp,
  FolderOpen,
  LayoutDashboard,
  Library,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Shield,
  ScanSearch,
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
  { to: '/evaluations', label: 'Evaluations', icon: ClipboardList, exact: true },
] as const;

const adminNavItems: readonly NavItem[] = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/admin/users', label: 'Users', icon: Users, exact: true },
  { to: '/admin/ingest', label: 'Ingest', icon: FileUp, exact: true },
  { to: '/admin/references', label: 'References', icon: Library, exact: true },
  { to: '/matrix', label: 'Monitoring Matrix', icon: Shield, exact: true },
  { to: '/admin/model-validation', label: 'Model Validation', icon: ScanSearch, exact: true },
  { to: '/admin/prompts', label: 'Prompts', icon: Settings, exact: false },
  { to: '/admin/preferences', label: 'Logs', icon: BookOpen, exact: true },
] as const;

function NavLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const Icon = item.icon;

  const baseClass = cn(
    'group flex h-10 items-center rounded-sm text-sm font-medium text-slate-600 transition-colors hover:bg-slate-200/50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
    collapsed ? 'justify-center px-0' : 'gap-3 pl-3 pr-3',
  );

  const activeClass = cn(
    'group flex h-10 items-center rounded-sm text-sm font-semibold text-slate-900 bg-slate-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
    collapsed ? 'justify-center px-0' : 'gap-3 pl-3 pr-3',
  );

  return (
    <Link
      to={item.to}
      activeOptions={{ exact: item.exact }}
      className={baseClass}
      activeProps={{ className: activeClass }}
      title={collapsed ? item.label : undefined}
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );
}

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
        'fixed bottom-0 left-0 top-0 z-50 flex flex-col border-r border-slate-200 bg-slate-50 transition-[width] duration-200',
        asideWidth,
      )}
    >
      {/* Brand / Logo */}
      <div
        className={cn(
          'flex h-16 shrink-0 items-center border-b border-slate-200',
          collapsed ? 'justify-center px-2' : 'gap-3 px-4',
        )}
      >
        <img src="/lspu-logo.png" alt="LSPU" className="size-9 shrink-0 object-contain" />
        {!collapsed && (
          <div className="flex flex-col leading-none">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              LSPU
            </span>
            <span className="text-base font-bold tracking-tight text-slate-900 mt-0.5">
              EquipED
            </span>
          </div>
        )}
      </div>

      {/* ── Navigation Container ───────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto py-4">
        <nav aria-label="Primary" className="grid gap-1 px-3">
          {!isAdmin && (
            <>
              {workspaceNavItems.map((item) => (
                <NavLink key={item.to} item={item} collapsed={collapsed} />
              ))}
            </>
          )}

          {isAdmin && (
            <>
              {adminNavItems.map((item) => (
                <NavLink key={item.to} item={item} collapsed={collapsed} />
              ))}
            </>
          )}
        </nav>

        <div className="mx-3 my-4 border-t border-slate-200" />

        <nav aria-label="Secondary" className="grid gap-1 px-3">
          {isAdmin && (
            <Link
              to="/admin/rubrics"
              activeOptions={{ exact: true }}
              className={cn(
                'group flex h-10 items-center rounded-sm text-sm font-medium text-slate-600 transition-colors hover:bg-slate-200/50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
                collapsed ? 'justify-center px-0' : 'gap-3 pl-3 pr-3',
              )}
              activeProps={{
                className: cn(
                  'group flex h-10 items-center rounded-sm text-sm font-semibold text-slate-900 bg-slate-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
                  collapsed ? 'justify-center px-0' : 'gap-3 pl-3 pr-3',
                ),
              }}
              title={collapsed ? 'Rubrics' : undefined}
            >
              <Upload className="size-4 shrink-0" aria-hidden="true" />
              {!collapsed && <span className="truncate">Rubrics</span>}
            </Link>
          )}
        </nav>
      </div>

      {/* ── Bottom Collapse Toggle ──────────────────────────────────────── */}
      <div
        className={cn(
          'flex h-12 shrink-0 items-center px-3 border-t border-slate-200 mt-auto',
          collapsed ? 'justify-center' : 'justify-end',
        )}
      >
        <button
          type="button"
          onClick={onToggle}
          className="flex size-9 items-center justify-center rounded-sm text-slate-500 transition-colors hover:bg-slate-200/60 hover:text-slate-900"
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
