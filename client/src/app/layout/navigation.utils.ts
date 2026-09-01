import {
  BookOpen,
  BookOpenText,
  Books,
  ClipboardText,
  FolderOpen,
  Gear,
  GitFork,
  type Icon,
  ListChecks,
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

export const facultyNavGroups: readonly NavGroup[] = [
  {
    id: 'home',
    label: 'HOME',
    items: [
      { to: '/dashboard', label: 'Home', icon: SquaresFour, exact: true },
    ],
  },
  {
    id: 'workspace',
    label: 'WORKSPACE',
    items: [
      { to: '/documents', label: 'My SLMs', icon: FolderOpen, exact: false },
      { to: '/evaluations', label: 'Evaluations', icon: ClipboardText, exact: false },
    ],
  },
  {
    id: 'alignment',
    label: 'ALIGNMENT',
    items: [
      { to: '/syllabus-alignment', label: 'Syllabus Alignment', icon: ListChecks, exact: false },
      { to: '/alignment', label: 'Curriculum Check', icon: BookOpenText, exact: false },
    ],
  },
] as const;

export const facultySecondaryNavItems: readonly NavItem[] = [] as const;

export const adminNavGroups: readonly NavGroup[] = [
  {
    id: 'overview',
    label: 'OVERVIEW',
    items: [
      { to: '/admin', label: 'Dashboard', icon: SquaresFour, exact: true },
    ],
  },
  {
    id: 'operations',
    label: 'OPERATIONS',
    items: [
      { to: '/admin/users', label: 'User Management', icon: Users, exact: true },
      { to: '/matrix', label: 'Monitoring Matrix', icon: Shield, exact: true },
    ],
  },
  {
    id: 'knowledge-base',
    label: 'KNOWLEDGE BASE',
    items: [
      { to: '/admin/ingest', label: 'Reference Ingestion', icon: UploadSimple, exact: true },
      { to: '/admin/references', label: 'Reference Library', icon: Books, exact: true },
      { to: '/admin/rubrics', label: 'Rubric Editor', icon: ClipboardText, exact: true },
    ],
  },
  {
    id: 'model-governance',
    label: 'MODEL GOVERNANCE',
    items: [
      { to: '/evaluation-map', label: 'Knowledge Map', icon: GitFork, exact: true },
      { to: '/admin/model-validation', label: 'Model Validation', icon: Scan, exact: true },
      { to: '/admin/prompts', label: 'Agent Prompts', icon: Gear, exact: false },
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
    headerLeft: isCollapsed ? 'left-0 md:left-[5.75rem]' : 'left-0 md:left-72',
    mainPadding: isCollapsed ? 'pl-0 md:pl-[5.75rem]' : 'pl-0 md:pl-72',
    sidebarDesktopWidth: isCollapsed ? 'md:w-[5.75rem]' : 'md:w-72',
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

export function getBreadcrumbs(pathname: string, userRole?: string): BreadcrumbItem[] {
  const cleanPath = pathname.split('?')[0].replace(/\/+$/, '') || '/';

  if (cleanPath === '/dashboard' || cleanPath === '/') {
    return [
      { label: 'Faculty Workspace' },
      { label: 'Overview' },
    ];
  }

  if (cleanPath.startsWith('/documents/') && cleanPath.endsWith('/evaluation')) {
    return [
      { label: 'My SLMs', to: '/documents' },
      { label: 'Evaluation Setup' },
    ];
  }

  if (cleanPath === '/documents') {
    return [
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'My SLMs' },
    ];
  }

  if (cleanPath === '/upload') {
    return [
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'Upload SLM' },
    ];
  }

  if (cleanPath.startsWith('/evaluations/') && cleanPath.endsWith('/report')) {
    return [
      { label: 'Evaluations', to: '/evaluations' },
      { label: 'Evaluation Report' },
    ];
  }

  if (cleanPath.startsWith('/evaluations/') && cleanPath !== '/evaluations') {
    return [
      { label: 'Evaluations', to: '/evaluations' },
      { label: 'Scorecard' },
    ];
  }

  if (cleanPath === '/evaluations') {
    return [
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'Evaluations' },
    ];
  }

  if (cleanPath.startsWith('/syllabus-alignment/') && cleanPath.endsWith('/report')) {
    return [
      { label: 'Syllabus Alignment', to: '/syllabus-alignment' },
      { label: 'Alignment Report' },
    ];
  }

  if (cleanPath.startsWith('/syllabus-alignment/') && cleanPath !== '/syllabus-alignment') {
    return [
      { label: 'Syllabus Alignment', to: '/syllabus-alignment' },
      { label: 'Workspace' },
    ];
  }

  if (cleanPath === '/syllabus-alignment') {
    return [
      { label: 'Alignment', to: '/dashboard' },
      { label: 'Syllabus Alignment' },
    ];
  }

  if (cleanPath === '/alignment') {
    return [
      { label: 'Alignment', to: '/dashboard' },
      { label: 'Curriculum Check' },
    ];
  }

  if (cleanPath === '/matrix') {
    return [
      { label: 'Institutional Admin', to: userRole === 'admin' ? '/admin' : '/dashboard' },
      { label: 'Monitoring Matrix' },
    ];
  }

  if (cleanPath === '/evaluation-map') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Knowledge Map' },
    ];
  }

  if (cleanPath === '/admin') {
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

  if (cleanPath === '/admin/references') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Reference Library' },
    ];
  }

  if (cleanPath === '/admin/ingest') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Reference Ingestion' },
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

  if (cleanPath === '/admin/prompts') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Agent Prompts' },
    ];
  }

  if (cleanPath === '/admin/preferences') {
    return [
      { label: 'Administration', to: '/admin' },
      { label: 'Preference Logs' },
    ];
  }

  return [
    { label: 'EquipED' },
  ];
}

export function getRouteTitle(routeId?: string, userRole?: string): string {
  if (!routeId) return 'EquipED';

  if (routeId.includes('/dashboard')) return 'Home';
  if (routeId.includes('/documents/') && routeId.includes('/evaluation'))
    return 'Evaluation Interface';
  if (routeId.includes('/documents')) return 'My SLMs';
  if (routeId.includes('/upload')) return 'Upload SLM';
  if (routeId.includes('/evaluations') && routeId.includes('/report'))
    return 'Evaluation Report';
  if (
    routeId.includes('/evaluations/$id') ||
    (routeId.startsWith('/evaluations/') && routeId !== '/evaluations') ||
    (routeId.includes('/evaluations/') && !routeId.endsWith('/evaluations'))
  ) {
    return 'Scorecard';
  }
  if (routeId.includes('/evaluations')) return 'Evaluations';
  if (routeId.includes('/evaluation-map')) return 'Knowledge Map';
  if (routeId.includes('/syllabus-alignment') && routeId.includes('/report'))
    return 'Syllabus Alignment Report';
  if (
    routeId.includes('/syllabus-alignment/$documentId') ||
    (routeId.startsWith('/syllabus-alignment/') && routeId !== '/syllabus-alignment')
  ) {
    return 'Syllabus Alignment Workspace';
  }
  if (routeId.includes('/syllabus-alignment')) return 'Syllabus Alignment';
  if (routeId.includes('/alignment')) return 'Curriculum Check';
  if (routeId.includes('/matrix')) return 'Monitoring Matrix';
  if (routeId.includes('/admin/users')) return 'User Management';
  if (routeId.includes('/admin/ingest')) return 'Reference Ingestion';
  if (routeId.includes('/admin/references')) return 'Reference Library';
  if (routeId.includes('/admin/prompts')) return 'Agent Prompts';
  if (routeId.includes('/admin/preferences')) return 'Preference Logs';
  if (routeId.includes('/admin/rubrics')) return 'Rubric Editor';
  if (routeId.includes('/admin/model-validation')) return 'Model Validation';
  if (routeId.includes('/admin')) return 'Admin Dashboard';

  return 'EquipED';
}
