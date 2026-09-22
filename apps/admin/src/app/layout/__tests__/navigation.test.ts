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
  it('organizes admin navigation with descriptive institutional two-word names', () => {
    expect(adminNavGroups.map(({ id, label }) => ({ id, label }))).toEqual([
      { id: 'overview', label: 'Overview' },
      { id: 'operations', label: 'Operations' },
      { id: 'knowledge-base', label: 'Knowledge Base' },
      { id: 'model-governance', label: 'Model Governance' },
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
      { to: '/admin/training-data', label: 'Training Data' },
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

  it('returns Reference Ingestion for /admin/ingest', () => {
    expect(getRouteTitle('/admin/ingest')).toBe('Reference Ingestion');
  });

  it('returns Reference Library for /admin/references', () => {
    expect(getRouteTitle('/admin/references')).toBe('Reference Library');
  });

  it('returns Rubric Editor for /admin/rubrics', () => {
    expect(getRouteTitle('/admin/rubrics')).toBe('Rubric Editor');
  });

  it('returns Model Validation for /admin/model-validation', () => {
    expect(getRouteTitle('/admin/model-validation')).toBe('Model Validation');
  });
});

describe('getBreadcrumbs', () => {
  it('returns Dashboard for /admin without duplicate root', () => {
    expect(getBreadcrumbs('/admin')).toEqual([
      { label: 'Dashboard' },
    ]);
  });

  it('returns User Management for /admin/users', () => {
    expect(getBreadcrumbs('/admin/users')).toEqual([
      { label: 'User Management' },
    ]);
  });

  it('returns Monitoring Matrix for /matrix', () => {
    expect(getBreadcrumbs('/matrix')).toEqual([
      { label: 'Monitoring Matrix' },
    ]);
  });

  it('returns Monitoring Matrix > Master Synthesis for /matrix/:documentId', () => {
    expect(getBreadcrumbs('/matrix/doc-123')).toEqual([
      { label: 'Monitoring Matrix', to: '/matrix' },
      { label: 'Master Synthesis' },
    ]);
  });

  it('returns Agent Prompts > Coordinator for /admin/prompts/coordinator', () => {
    expect(getBreadcrumbs('/admin/prompts/coordinator')).toEqual([
      { label: 'Agent Prompts', to: '/admin/prompts' },
      { label: 'Coordinator' },
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
    expect(classes.headerLeft).toBe('left-0 md:left-64');
    expect(classes.mainPadding).toBe('pl-0 md:pl-64');
    expect(classes.sidebarDesktopWidth).toBe('md:w-64');
  });

  it('returns collapsed desktop layout classes when isCollapsed is true', () => {
    const classes = getSidebarLayoutClasses(true);
    expect(classes.headerLeft).toBe('left-0 md:left-[4.5rem]');
    expect(classes.mainPadding).toBe('pl-0 md:pl-[4.5rem]');
    expect(classes.sidebarDesktopWidth).toBe('md:w-[4.5rem]');
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
