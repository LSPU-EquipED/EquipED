import {
  BookOpenText,
  ClipboardText,
  FolderOpen,
  GraduationCap,
  type Icon,
  Lightbulb,
  ListChecks,
  ShieldCheck,
  SquaresFour,
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

export function getBreadcrumbs(pathname: string): BreadcrumbItem[] {
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

  if (cleanPath === '/evaluations') {
    return [
      { label: 'Evaluations' },
      { label: 'History' },
    ];
  }

  if (cleanPath.startsWith('/evaluations/')) {
    return [
      { label: 'Evaluations', to: '/evaluations' },
      { label: 'Evaluation Results' },
    ];
  }

  if (cleanPath.startsWith('/syllabus-alignment/') && cleanPath.endsWith('/report')) {
    return [
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'Syllabus Alignment', to: '/syllabus-alignment' },
      { label: 'Alignment Report' },
    ];
  }

  if (cleanPath === '/syllabus-alignment') {
    return [
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'Syllabus Alignment' },
    ];
  }

  if (cleanPath.startsWith('/syllabus-alignment/')) {
    return [
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'Syllabus Alignment', to: '/syllabus-alignment' },
      { label: 'Workstation' },
    ];
  }

  if (cleanPath === '/alignment') {
    return [
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'Curriculum Check' },
    ];
  }

  return [
    { label: 'Faculty Workspace', to: '/dashboard' },
    { label: 'Portal' },
  ];
}

export function getRouteTitle(pathname: string): string {
  const cleanPath = pathname.split('?')[0].replace(/\/+$/, '') || '/';
  if (cleanPath === '/dashboard' || cleanPath === '/') return 'Home';
  if (cleanPath === '/documents') return 'My SLMs';
  if (cleanPath.startsWith('/documents/') && cleanPath.endsWith('/evaluation')) return 'Specialist Review';
  if (cleanPath === '/evaluations') return 'Evaluation History';
  if (cleanPath.startsWith('/evaluations/')) return 'Scorecard';
  if (cleanPath === '/alignment') return 'Curriculum Check';
  return 'EquipED';
}
