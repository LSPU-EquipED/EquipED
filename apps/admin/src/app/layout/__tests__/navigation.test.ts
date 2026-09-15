import { describe, expect, it } from 'vitest';
import {
  adminNavGroups,
  getAriaCurrent,
  getBreadcrumbs,
  getRouteTitle,
  getSidebarInertState,
  getSidebarLayoutClasses,
  isNavigationActive,
} from '../navigation.utils';

describe('isNavigationActive', () => {
  it('matches exact routes strictly when exact is true', () => {
    expect(isNavigationActive('/admin', '/admin', true)).toBe(true);
    expect(isNavigationActive('/admin/users', '/admin', true)).toBe(false);
  });

  it('matches child routes when exact is false', () => {
    expect(isNavigationActive('/admin/prompts', '/admin/prompts', false)).toBe(true);
    expect(isNavigationActive('/admin/prompts/coordinator', '/admin/prompts', false)).toBe(true);
    expect(isNavigationActive('/matrix', '/matrix', false)).toBe(true);
    expect(isNavigationActive('/evaluation-map', '/evaluation-map', false)).toBe(true);
  });
});

describe('admin navigation group structure', () => {
  it('organizes admin navigation by responsibility without losing routes', () => {
    expect(adminNavGroups.map(({ id, label }) => ({ id, label }))).toEqual([
      { id: 'overview', label: 'OVERVIEW' },
      { id: 'operations', label: 'OPERATIONS' },
      { id: 'knowledge-base', label: 'KNOWLEDGE BASE' },
      { id: 'model-governance', label: 'MODEL GOVERNANCE' },
    ]);

    expect(adminNavGroups.flatMap((group) => group.items).map(({ to, label }) => ({ to, label }))).toEqual([
      { to: '/admin', label: 'Dashboard' },
      { to: '/admin/users', label: 'User Management' },
      { to: '/matrix', label: 'Monitoring Matrix' },
      { to: '/admin/ingest', label: 'Reference Ingestion' },
      { to: '/admin/references', label: 'Reference Library' },
      { to: '/admin/rubrics', label: 'Rubric Editor' },
      { to: '/evaluation-map', label: 'Knowledge Map' },
      { to: '/admin/model-validation', label: 'Model Validation' },
      { to: '/admin/prompts', label: 'Agent Prompts' },
      { to: '/admin/preferences', label: 'Preference Logs' },
    ]);
  });
});

describe('getRouteTitle', () => {
  it('returns Dashboard for /admin', () => {
    expect(getRouteTitle('/admin')).toBe('Dashboard');
  });

  it('returns User Management for /admin/users', () => {
    expect(getRouteTitle('/admin/users')).toBe('User Management');
  });

  it('returns Monitoring Matrix for /matrix', () => {
    expect(getRouteTitle('/matrix')).toBe('Monitoring Matrix');
  });

  it('returns Knowledge Map for /evaluation-map', () => {
    expect(getRouteTitle('/evaluation-map')).toBe('Knowledge Map');
  });
});

describe('getBreadcrumbs', () => {
  it('returns Administration > Dashboard for /admin', () => {
    expect(getBreadcrumbs('/admin')).toEqual([
      { label: 'Administration' },
      { label: 'Dashboard' },
    ]);
  });

  it('returns Administration > User Management for /admin/users', () => {
    expect(getBreadcrumbs('/admin/users')).toEqual([
      { label: 'Administration', to: '/admin' },
      { label: 'User Management' },
    ]);
  });

  it('returns Administration > Monitoring Matrix for /matrix', () => {
    expect(getBreadcrumbs('/matrix')).toEqual([
      { label: 'Administration', to: '/admin' },
      { label: 'Monitoring Matrix' },
    ]);
  });
});

describe('getAriaCurrent', () => {
  it('returns page when active is true', () => {
    expect(getAriaCurrent(true)).toBe('page');
  });

  it('returns undefined when active is false', () => {
    expect(getAriaCurrent(false)).toBeUndefined();
  });
});

describe('getSidebarLayoutClasses', () => {
  it('returns uncollapsed desktop layout classes when isCollapsed is false', () => {
    const classes = getSidebarLayoutClasses(false);
    expect(classes.headerLeft).toBe('left-0 md:left-72');
    expect(classes.mainPadding).toBe('pl-0 md:pl-72');
    expect(classes.sidebarDesktopWidth).toBe('md:w-72');
  });

  it('returns collapsed desktop layout classes when isCollapsed is true', () => {
    const classes = getSidebarLayoutClasses(true);
    expect(classes.headerLeft).toBe('left-0 md:left-[5.75rem]');
    expect(classes.mainPadding).toBe('pl-0 md:pl-[5.75rem]');
    expect(classes.sidebarDesktopWidth).toBe('md:w-[5.75rem]');
  });
});

describe('getSidebarInertState', () => {
  it('returns inert false when not mobile regardless of open status', () => {
    expect(getSidebarInertState(false, false)).toEqual({ inert: false, ariaHidden: false });
    expect(getSidebarInertState(false, true)).toEqual({ inert: false, ariaHidden: false });
  });

  it('returns inert true when mobile and closed', () => {
    expect(getSidebarInertState(true, false)).toEqual({ inert: true, ariaHidden: true });
  });

  it('returns inert false when mobile and open', () => {
    expect(getSidebarInertState(true, true)).toEqual({ inert: false, ariaHidden: false });
  });
});
