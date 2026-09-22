import {
  BookOpen,
  Books,
  ClipboardText,
  Gear,
  GitFork,
  GraduationCap,
  type Icon,
  Scan,
  Shield,
  SquaresFour,
  UploadSimple,
  Users,
} from '@phosphor-icons/react';

export interface NavItem {
  to: string;
  label: string;
  icon: Icon;
  exact: boolean;
}

export interface BreadcrumbItem {
  label: string;
  to?: string;
}

export interface NavGroup {
  id: string;
  label: string;
  items: readonly NavItem[];
}

export const adminNavGroups: readonly NavGroup[] = [
  {
    id: 'overview',
    label: 'Overview',
    items: [
      { to: '/admin', label: 'Dashboard', icon: SquaresFour, exact: true },
    ],
  },
  {
    id: 'operations',
    label: 'Operations',
    items: [
      { to: '/admin/users', label: 'User Management', icon: Users, exact: true },
      { to: '/matrix', label: 'Monitoring Matrix', icon: Shield, exact: true },
    ],
  },
  {
    id: 'knowledge-base',
    label: 'Knowledge base',
    items: [
      { to: '/admin/ingest', label: 'Reference Ingestion', icon: UploadSimple, exact: true },
      { to: '/admin/references', label: 'Reference Library', icon: Books, exact: true },
      { to: '/admin/rubrics', label: 'Rubric Editor', icon: ClipboardText, exact: true },
    ],
  },
  {
    id: 'model-governance',
    label: 'Model governance',
    items: [
      { to: '/evaluation-map', label: 'Knowledge Map', icon: GitFork, exact: true },
      { to: '/admin/model-validation', label: 'Model Validation', icon: Scan, exact: true },
      { to: '/admin/prompts', label: 'Agent Prompts', icon: Gear, exact: false },
      { to: '/admin/training-data', label: 'Training Data', icon: GraduationCap, exact: false },
      { to: '/admin/preferences', label: 'Preference Logs', icon: BookOpen, exact: true },
    ],
  },
] as const;

export function isNavigationActive(
  currentPath: string,
  targetPath: string,
  exact: boolean,
): boolean {
  if (exact) {
    return currentPath === targetPath;
  }
  if (currentPath === targetPath) {
    return true;
  }
  const prefix = targetPath.endsWith('/') ? targetPath : `${targetPath}/`;
  return currentPath.startsWith(prefix);
}

export function getAriaCurrent(isActive: boolean): 'page' | undefined {
  return isActive ? 'page' : undefined;
}

export function getSidebarLayoutClasses(isCollapsed: boolean): {
  headerLeft: string;
  mainPadding: string;
  sidebarDesktopWidth: string;
} {
  return {
    headerLeft: isCollapsed ? 'left-0 md:left-[4.5rem]' : 'left-0 md:left-64',
    mainPadding: isCollapsed ? 'pl-0 md:pl-[4.5rem]' : 'pl-0 md:pl-64',
    sidebarDesktopWidth: isCollapsed ? 'md:w-[4.5rem]' : 'md:w-64',
  };
}

export function getSidebarInertState(
  isMobile: boolean,
  mobileOpen: boolean,
): {
  inert: boolean;
  ariaHidden: boolean;
} {
  if (!isMobile) {
    return { inert: false, ariaHidden: false };
  }
  return {
    inert: !mobileOpen,
    ariaHidden: !mobileOpen,
  };
}

export function getBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const cleanPath = pathname.split('?')[0].replace(/\/+$/, '') || '/';

  if (cleanPath === '/admin' || cleanPath === '/') {
    return [
      { label: 'Administration' },
      { label: 'Dashboard' },
    ];
  }

  if (cleanPath === '/admin/users') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'User Management' },
    ];
  }

  if (cleanPath === '/admin/ingest') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Reference Ingestion' },
    ];
  }

  if (cleanPath === '/admin/references') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Reference Library' },
    ];
  }

  if (cleanPath === '/admin/rubrics') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Rubric Editor' },
    ];
  }

  if (cleanPath === '/admin/model-validation') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Model Validation' },
    ];
  }

  if (cleanPath === '/admin/preferences') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Preference Logs' },
    ];
  }

  if (cleanPath === '/admin/prompts' || cleanPath.startsWith('/admin/prompts/')) {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Agent Prompts' },
    ];
  }

  if (cleanPath === '/admin/training-data' || cleanPath.startsWith('/admin/training-data/')) {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Training Data' },
    ];
  }

  if (cleanPath.startsWith('/admin/synthesis/')) {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Master Synthesis' },
    ];
  }

  if (cleanPath === '/matrix') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Monitoring Matrix' },
    ];
  }

  if (cleanPath.startsWith('/matrix/')) {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Monitoring Matrix', to: '/matrix' },
      { label: 'Synthesis Detail' },
    ];
  }

  if (cleanPath === '/evaluation-map') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Knowledge Map' },
    ];
  }

  return [
    { label: 'Administration', to: '/admin' },
    { label: 'Workspace' },
  ];
}

export function getRouteTitle(pathname: string): string {
  const cleanPath = pathname.split('?')[0].replace(/\/+$/, '') || '/';
  if (cleanPath === '/admin' || cleanPath === '/') return 'Dashboard';
  if (cleanPath === '/admin/users') return 'User Management';
  if (cleanPath === '/matrix') return 'Monitoring Matrix';
  if (cleanPath === '/evaluation-map') return 'Knowledge Map';
  if (cleanPath === '/admin/ingest') return 'Reference Ingestion';
  if (cleanPath === '/admin/references') return 'Reference Library';
  if (cleanPath === '/admin/rubrics') return 'Rubric Editor';
  if (cleanPath === '/admin/model-validation') return 'Model Validation';
  if (cleanPath.startsWith('/admin/prompts')) return 'Agent Prompts';
  if (cleanPath.startsWith('/admin/training-data')) return 'Training Data';
  if (cleanPath === '/admin/preferences') return 'Preference Logs';
  return 'EquipED Admin';
}
