import {
  BookOpenText,
  ClockCounterClockwise,
  FileText,
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
    label: 'Home',
    items: [
      { to: '/dashboard', label: 'Overview', icon: SquaresFour, exact: true },
    ],
  },
  {
    id: 'storage',
    label: 'Documents',
    items: [
      { to: '/documents', label: 'Documents', icon: FolderOpen, exact: false },
    ],
  },
  {
    id: 'specialists',
    label: 'Evaluations',
    items: [
      { to: '/specialists/sme', label: 'SME', icon: GraduationCap, exact: false },
      { to: '/specialists/coordinator', label: 'Coordinator', icon: ListChecks, exact: false },
      { to: '/specialists/gad', label: 'GAD', icon: ShieldCheck, exact: false },
      { to: '/specialists/itso', label: 'ITSO', icon: Lightbulb, exact: false },
    ],
  },
  {
    id: 'alignment',
    label: 'Alignment',
    items: [
      { to: '/syllabus-alignment', label: 'Syllabus', icon: FileText, exact: false },
      { to: '/curriculum-alignment', label: 'Curriculum', icon: BookOpenText, exact: false },
    ],
  },
  {
    id: 'logs',
    label: 'Logs',
    items: [
      { to: '/evaluations', label: 'History', icon: ClockCounterClockwise, exact: true },
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

  const permSet = new Set(permissions);

  return groups
    .map((group) => {
      if (group.id !== 'specialists') {
        return group;
      }
      const filteredItems = group.items.filter((item) => {
        const requiredPerm = SPECIALIST_PERMS[item.to];
        if (!requiredPerm) return true;
        return permSet.has(requiredPerm);
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

  if (cleanPath === '/dashboard' || cleanPath === '/') {
    return [{ label: 'Overview' }];
  }

  if (cleanPath === '/documents' || cleanPath === '/storage') {
    return [{ label: 'Documents' }];
  }

  if (cleanPath.startsWith('/documents/') && cleanPath.endsWith('/evaluation')) {
    return [
      { label: 'Documents', to: '/documents' },
      { label: 'Review' },
    ];
  }

  if (cleanPath.startsWith('/specialists/sme/')) {
    return [
      { label: 'SME', to: '/specialists/sme' },
      { label: 'Scoreboard' },
    ];
  }

  if (cleanPath === '/specialists/sme') {
    return [{ label: 'SME' }];
  }

  if (cleanPath.startsWith('/specialists/coordinator/')) {
    return [
      { label: 'Coordinator', to: '/specialists/coordinator' },
      { label: 'Scoreboard' },
    ];
  }

  if (cleanPath === '/specialists/coordinator') {
    return [{ label: 'Coordinator' }];
  }

  if (cleanPath.startsWith('/specialists/gad/')) {
    return [
      { label: 'GAD', to: '/specialists/gad' },
      { label: 'Scoreboard' },
    ];
  }

  if (cleanPath === '/specialists/gad') {
    return [{ label: 'GAD' }];
  }

  if (cleanPath.startsWith('/specialists/itso/')) {
    return [
      { label: 'ITSO', to: '/specialists/itso' },
      { label: 'Scoreboard' },
    ];
  }

  if (cleanPath === '/specialists/itso') {
    return [{ label: 'ITSO' }];
  }

  if (cleanPath === '/evaluations') {
    return [{ label: 'History' }];
  }

  if (cleanPath.startsWith('/evaluations/') && cleanPath.endsWith('/report')) {
    return [
      { label: 'History', to: '/evaluations' },
      { label: 'Report' },
    ];
  }

  if (cleanPath.startsWith('/evaluations/')) {
    return [
      { label: 'History', to: '/evaluations' },
      { label: 'Scorecard' },
    ];
  }

  if (cleanPath.startsWith('/syllabus-alignment/') && cleanPath.endsWith('/report')) {
    return [
      { label: 'Syllabus', to: '/syllabus-alignment' },
      { label: 'Report' },
    ];
  }

  if (cleanPath.startsWith('/syllabus-alignment/')) {
    return [
      { label: 'Syllabus', to: '/syllabus-alignment' },
      { label: 'Workstation' },
    ];
  }

  if (cleanPath === '/syllabus-alignment') {
    return [{ label: 'Syllabus' }];
  }

  if (cleanPath.startsWith('/curriculum-alignment/')) {
    return [
      { label: 'Curriculum', to: '/curriculum-alignment' },
      { label: 'Matrix' },
    ];
  }

  if (cleanPath === '/curriculum-alignment') {
    return [{ label: 'Curriculum' }];
  }

  return [{ label: 'Portal' }];
}

export function getRouteTitle(pathname: string): string {
  const cleanPath = pathname.split('?')[0].replace(/\/+$/, '') || '/';
  if (cleanPath === '/dashboard' || cleanPath === '/') return 'Overview';
  if (cleanPath === '/documents') return 'Documents';
  if (cleanPath.startsWith('/documents/') && cleanPath.endsWith('/evaluation')) return 'Review';
  if (cleanPath === '/specialists/sme') return 'SME';
  if (cleanPath === '/specialists/coordinator') return 'Coordinator';
  if (cleanPath === '/specialists/gad') return 'GAD';
  if (cleanPath === '/specialists/itso') return 'ITSO';
  if (cleanPath === '/evaluations') return 'History';
  if (cleanPath.startsWith('/evaluations/')) return 'Scorecard';
  if (cleanPath === '/syllabus-alignment') return 'Syllabus';
  if (cleanPath.startsWith('/syllabus-alignment/') && cleanPath.endsWith('/report')) return 'Report';
  if (cleanPath.startsWith('/syllabus-alignment/')) return 'Workstation';
  if (cleanPath === '/curriculum-alignment') return 'Curriculum';
  return 'EquipED';
}
