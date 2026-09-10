import {
  BookOpen,
  BookOpenText,
  Books,
  ClipboardText,
  FolderOpen,
  Gear,
  GitFork,
  GraduationCap,
  type Icon,
  Lightbulb,
  ListChecks,
  Scan,
  Shield,
  ShieldCheck,
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
    id: 'storage',
    label: 'SLM REPOSITORY',
    items: [
      { to: '/documents', label: 'SLM Storage', icon: FolderOpen, exact: false },
    ],
  },
  {
    id: 'specialists',
    label: 'EVALUATION SPECIALISTS',
    items: [
      { to: '/specialists/sme', label: 'Subject Matter Expert', icon: GraduationCap, exact: false },
      { to: '/specialists/coordinator', label: 'Program Coordinator', icon: ListChecks, exact: false },
      { to: '/specialists/gad', label: 'Gender & Development', icon: ShieldCheck, exact: false },
      { to: '/specialists/itso', label: 'Innovation & IP (ITSO)', icon: Lightbulb, exact: false },
    ],
  },
  {
    id: 'alignment',
    label: 'ALIGNMENT & AUDIT',
    items: [
      { to: '/syllabus-alignment', label: 'Syllabus Alignment', icon: ListChecks, exact: false },
      { to: '/alignment', label: 'Curriculum Check', icon: BookOpenText, exact: false },
      { to: '/evaluations', label: 'Evaluation History', icon: ClipboardText, exact: true },
    ],
  },
] as const;

export const facultySecondaryNavItems: readonly NavItem[] = [] as const;

export function filterFacultyNavGroups(
  groups: readonly NavGroup[],
  permissions?: readonly string[] | null,
): readonly NavGroup[] {
  if (
    permissions === undefined ||
    permissions === null ||
    permissions.length === 0
  ) {
    return groups;
  }

  const SPECIALIST_PERMS: Record<string, string> = {
    '/specialists/sme': 'sme',
    '/specialists/coordinator': 'coordinator',
    '/specialists/gad': 'gad',
    '/specialists/itso': 'itso',
  };

  return groups
    .map((group) => {
      if (group.id !== 'specialists') {
        return group;
      }
      const filteredItems = group.items.filter((item) => {
        const requiredPerm = SPECIALIST_PERMS[item.to];
        if (!requiredPerm) return true;
        return permissions.includes(requiredPerm);
      });
      return {
        ...group,
        items: filteredItems,
      };
    })
    .filter((group) => group.items.length > 0);
}

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
      { label: 'SLM Storage', to: '/documents' },
      { label: 'Specialist Review' },
    ];
  }

  if (cleanPath === '/documents' || cleanPath === '/storage') {
    return [
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'SLM Storage' },
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

  if (cleanPath.startsWith('/specialists/sme')) {
    return [
      { label: 'Specialists', to: '/dashboard' },
      { label: 'Subject Matter Expert' },
    ];
  }

  if (cleanPath.startsWith('/specialists/coordinator')) {
    return [
      { label: 'Specialists', to: '/dashboard' },
      { label: 'Program Coordinator' },
    ];
  }

  if (cleanPath.startsWith('/specialists/gad')) {
    return [
      { label: 'Specialists', to: '/dashboard' },
      { label: 'Gender & Development' },
    ];
  }

  if (cleanPath.startsWith('/specialists/itso')) {
    return [
      { label: 'Specialists', to: '/dashboard' },
      { label: 'Innovation & IP (ITSO)' },
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
      { label: 'Evaluation History' },
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
      { label: 'Administration', to: userRole === 'admin' ? '/admin' : '/dashboard' },
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

  if (cleanPath === '/admin/prompts' || cleanPath.startsWith('/admin/prompts/')) {
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
    return 'Specialist Review';
  if (routeId.includes('/documents')) return 'My SLMs';
  if (routeId.includes('/upload')) return 'Upload SLM';
  if (routeId.includes('/evaluations') && routeId.includes('/report'))
    return 'Evaluation Report';
  if (routeId.includes('/evaluations/$id')) return 'Scorecard';
  if (/^\/evaluations\/[^/]+$/.test(routeId)) return 'Scorecard';
  if (routeId.includes('/specialists')) return 'Specialist Review';
  if (routeId.includes('/evaluations')) return 'Evaluation History';
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
