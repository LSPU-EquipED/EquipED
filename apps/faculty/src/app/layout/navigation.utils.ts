import {
  BookOpenText,
  ClockCounterClockwise,
  FileText,
  FolderOpen,
  GraduationCap,
  Lightbulb,
  ListChecks,
  ShieldCheck,
  SquaresFour,
} from '@phosphor-icons/react';

import type { BreadcrumbItem, NavGroup, NavItem } from '@equiped/ui';

export type { NavItem, BreadcrumbItem, NavGroup } from '@equiped/ui';

export const facultyNavGroups: readonly NavGroup[] = [
  {
    id: 'home',
    label: 'Home',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: SquaresFour, exact: true },
    ],
  },
  {
    id: 'storage',
    label: 'Documents',
    items: [
      { to: '/documents', label: 'Module library', icon: FolderOpen, exact: false },
    ],
  },
  {
    id: 'specialists',
    label: 'Evaluations',
    items: [
      { to: '/specialists/sme', label: 'Subject Matter Expert', icon: GraduationCap, exact: false },
      { to: '/specialists/coordinator', label: 'Program Coordinator', icon: ListChecks, exact: false },
      { to: '/specialists/gad', label: 'Gender and Development', icon: ShieldCheck, exact: false },
      { to: '/specialists/itso', label: 'ITSO', icon: Lightbulb, exact: false },
    ],
  },
  {
    id: 'alignment',
    label: 'Alignment',
    items: [
      { to: '/syllabus-alignment', label: 'Syllabus check', icon: FileText, exact: false },
      { to: '/curriculum-alignment', label: 'Curriculum check', icon: BookOpenText, exact: false },
    ],
  },
  {
    id: 'logs',
    label: 'Records',
    items: [
      { to: '/evaluations', label: 'Evaluation history', icon: ClockCounterClockwise, exact: true },
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

export {
  isNavigationActive,
  getAriaCurrent,
  getSidebarLayoutClasses,
  getSidebarInertState,
} from '@equiped/ui';

export function getBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const cleanPath = pathname.split('?')[0].replace(/\/+$/, '') || '/';

  if (cleanPath === '/dashboard' || cleanPath === '/') {
    return [{ label: 'Dashboard' }];
  }

  if (cleanPath === '/documents' || cleanPath === '/storage') {
    return [{ label: 'Module library' }];
  }

  if (cleanPath.startsWith('/documents/') && cleanPath.endsWith('/evaluation')) {
    return [
      { label: 'Module library', to: '/documents' },
      { label: 'Review' },
    ];
  }

  if (cleanPath.startsWith('/specialists/sme/')) {
    return [
      { label: 'Subject Matter Expert', to: '/specialists/sme' },
      { label: 'Evaluation results' },
    ];
  }

  if (cleanPath === '/specialists/sme') {
    return [{ label: 'Subject Matter Expert' }];
  }

  if (cleanPath.startsWith('/specialists/coordinator/')) {
    return [
      { label: 'Program Coordinator', to: '/specialists/coordinator' },
      { label: 'Evaluation results' },
    ];
  }

  if (cleanPath === '/specialists/coordinator') {
    return [{ label: 'Program Coordinator' }];
  }

  if (cleanPath.startsWith('/specialists/gad/')) {
    return [
      { label: 'Gender and Development', to: '/specialists/gad' },
      { label: 'Evaluation results' },
    ];
  }

  if (cleanPath === '/specialists/gad') {
    return [{ label: 'Gender and Development' }];
  }

  if (cleanPath.startsWith('/specialists/itso/')) {
    return [
      { label: 'ITSO', to: '/specialists/itso' },
      { label: 'Evaluation results' },
    ];
  }

  if (cleanPath === '/specialists/itso') {
    return [{ label: 'ITSO' }];
  }

  if (cleanPath === '/evaluations') {
    return [{ label: 'Evaluation history' }];
  }

  if (cleanPath.startsWith('/evaluations/') && cleanPath.endsWith('/report')) {
    return [
      { label: 'Evaluation history', to: '/evaluations' },
      { label: 'Report' },
    ];
  }

  if (cleanPath.startsWith('/evaluations/')) {
    return [
      { label: 'Evaluation history', to: '/evaluations' },
      { label: 'Evaluation results' },
    ];
  }

  if (cleanPath.startsWith('/syllabus-alignment/') && cleanPath.endsWith('/report')) {
    return [
      { label: 'Syllabus check', to: '/syllabus-alignment' },
      { label: 'Report' },
    ];
  }

  if (cleanPath.startsWith('/syllabus-alignment/')) {
    return [
      { label: 'Syllabus check', to: '/syllabus-alignment' },
      { label: 'Workstation' },
    ];
  }

  if (cleanPath === '/syllabus-alignment') {
    return [{ label: 'Syllabus check' }];
  }

  if (cleanPath.startsWith('/curriculum-alignment/')) {
    return [
      { label: 'Curriculum check', to: '/curriculum-alignment' },
      { label: 'Matrix' },
    ];
  }

  if (cleanPath === '/curriculum-alignment') {
    return [{ label: 'Curriculum check' }];
  }

  return [{ label: 'Portal' }];
}

export function getRouteTitle(pathname: string): string {
  const cleanPath = pathname.split('?')[0].replace(/\/+$/, '') || '/';
  if (cleanPath === '/dashboard' || cleanPath === '/') return 'Dashboard';
  if (cleanPath === '/documents') return 'Module library';
  if (cleanPath.startsWith('/documents/') && cleanPath.endsWith('/evaluation')) return 'Review';
  if (cleanPath === '/specialists/sme') return 'Subject Matter Expert';
  if (cleanPath === '/specialists/coordinator') return 'Program Coordinator';
  if (cleanPath === '/specialists/gad') return 'Gender and Development';
  if (cleanPath === '/specialists/itso') return 'ITSO';
  if (/^\/specialists\/(sme|coordinator|gad|itso)\/[^/]+$/.test(cleanPath)) return 'Evaluation results';
  if (cleanPath === '/evaluations') return 'Evaluation history';
  if (cleanPath.startsWith('/evaluations/')) return 'Evaluation results';
  if (cleanPath === '/syllabus-alignment') return 'Syllabus check';
  if (cleanPath.startsWith('/syllabus-alignment/') && cleanPath.endsWith('/report')) return 'Report';
  if (cleanPath.startsWith('/syllabus-alignment/')) return 'Workstation';
  if (cleanPath === '/curriculum-alignment') return 'Curriculum check';
  return 'EquipED';
}
