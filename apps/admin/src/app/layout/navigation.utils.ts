import {
  BookOpen,
  Books,
  ClipboardText,
  Gear,
  GitFork,
  GraduationCap,
  Scan,
  Shield,
  SquaresFour,
  UploadSimple,
  Users,
} from '@phosphor-icons/react';
import type { BreadcrumbItem, NavGroup, NavItem } from '@equiped/ui';

export type { NavItem, BreadcrumbItem, NavGroup } from '@equiped/ui';

export {
  isNavigationActive,
  getAriaCurrent,
  getSidebarLayoutClasses,
  getSidebarInertState,
} from '@equiped/ui';

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
    label: 'Knowledge Base',
    items: [
      { to: '/admin/ingest', label: 'Reference Ingestion', icon: UploadSimple, exact: true },
      { to: '/admin/references', label: 'Reference Library', icon: Books, exact: true },
      { to: '/admin/rubrics', label: 'Rubric Editor', icon: ClipboardText, exact: true },
    ],
  },
  {
    id: 'model-governance',
    label: 'Model Governance',
    items: [
      { to: '/evaluation-map', label: 'Knowledge Map', icon: GitFork, exact: true },
      { to: '/admin/model-validation', label: 'Model Validation', icon: Scan, exact: true },
      { to: '/admin/prompts', label: 'Agent Prompts', icon: Gear, exact: false },
      { to: '/admin/training-data', label: 'Training Data', icon: GraduationCap, exact: false },
      { to: '/admin/preferences', label: 'Preference Logs', icon: BookOpen, exact: true },
    ],
  },
] as const;

export function getBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const cleanPath = pathname.split('?')[0].replace(/\/+$/, '') || '/';

  if (cleanPath === '/admin' || cleanPath === '/') {
    return [{ label: 'Dashboard' }];
  }

  if (cleanPath === '/admin/users') {
    return [{ label: 'User Management' }];
  }

  if (cleanPath === '/admin/ingest') {
    return [{ label: 'Reference Ingestion' }];
  }

  if (cleanPath === '/admin/references') {
    return [{ label: 'Reference Library' }];
  }

  if (cleanPath === '/admin/rubrics') {
    return [{ label: 'Rubric Editor' }];
  }

  if (cleanPath === '/admin/model-validation') {
    return [{ label: 'Model Validation' }];
  }

  if (cleanPath === '/admin/preferences') {
    return [{ label: 'Preference Logs' }];
  }

  if (cleanPath === '/admin/prompts') {
    return [{ label: 'Agent Prompts' }];
  }

  if (cleanPath.startsWith('/admin/prompts/')) {
    const agentId = cleanPath.replace('/admin/prompts/', '');
    const agentLabel = agentId.charAt(0).toUpperCase() + agentId.slice(1);
    return [
      { label: 'Agent Prompts', to: '/admin/prompts' },
      { label: agentLabel },
    ];
  }

  if (cleanPath === '/admin/training-data') {
    return [{ label: 'Training Data' }];
  }

  if (cleanPath.startsWith('/admin/training-data/')) {
    const agentId = cleanPath.replace('/admin/training-data/', '');
    const agentLabel = agentId.charAt(0).toUpperCase() + agentId.slice(1);
    return [
      { label: 'Training Data', to: '/admin/training-data' },
      { label: agentLabel },
    ];
  }

  if (cleanPath.startsWith('/admin/synthesis/')) {
    return [
      { label: 'Monitoring Matrix', to: '/matrix' },
      { label: 'Master Synthesis' },
    ];
  }

  if (cleanPath === '/matrix') {
    return [{ label: 'Monitoring Matrix' }];
  }

  if (cleanPath.startsWith('/matrix/')) {
    return [
      { label: 'Monitoring Matrix', to: '/matrix' },
      { label: 'Master Synthesis' },
    ];
  }

  if (cleanPath === '/evaluation-map') {
    return [{ label: 'Knowledge Map' }];
  }

  return [{ label: 'Workspace' }];
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
