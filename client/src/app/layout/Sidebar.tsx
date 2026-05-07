import { Link } from '@tanstack/react-router';
import {
  Archive,
  BookOpen,
  ChevronDown,
  ChevronsUpDown,
  FilePlus2,
  FolderOpen,
  GraduationCap,
  LayoutDashboard,
  Library,
  Settings,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/shared/components/utils';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const navItems = [
  { to: '/dashboard', label: 'Documents', icon: FolderOpen, exact: true },
  { to: '/upload', label: 'Upload', icon: FilePlus2, exact: true },
  { to: '/evaluations', label: 'Reviews', icon: Archive, exact: false },
  { to: '/matrix', label: 'Matrix', icon: LayoutDashboard, exact: true },
  { to: '/admin/prompts', label: 'Admin', icon: ShieldCheck, exact: false },
] as const;

const resourceItems = [
  { label: 'Rubrics', icon: BookOpen },
  { label: 'Guidelines', icon: GraduationCap },
  { label: 'Settings', icon: Settings },
] as const;

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const asideWidth = collapsed ? 'w-[5.75rem]' : 'w-72 max-md:w-[5.75rem]';

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
        {navItems.map((item) => {
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
      </nav>

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
          title={collapsed ? 'Marc Alberto' : undefined}
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold text-foreground">
            MA
          </span>
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">Marc Alberto</span>
                <span className="block truncate text-xs text-muted-foreground">m@example.com</span>
              </span>
              <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
