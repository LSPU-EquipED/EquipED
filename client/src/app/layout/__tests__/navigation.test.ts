import { describe, expect, it } from 'vitest';
import {
  facultyNavGroups,
  facultySecondaryNavItems,
  adminNavItems,
  getAriaCurrent,
  getBreadcrumbs,
  getRouteTitle,
  getSidebarInertState,
  getSidebarLayoutClasses,
  isNavigationActive,
} from '../navigation.utils';

describe('isNavigationActive', () => {
  it('matches exact routes strictly when exact is true', () => {
    expect(isNavigationActive('/dashboard', '/dashboard', true)).toBe(true);
    expect(isNavigationActive('/dashboard/extra', '/dashboard', true)).toBe(false);
    expect(isNavigationActive('/documents', '/dashboard', true)).toBe(false);
  });

  it('matches child routes when exact is false', () => {
    expect(isNavigationActive('/documents', '/documents', false)).toBe(true);
    expect(isNavigationActive('/documents/doc-123/evaluation', '/documents', false)).toBe(true);
    expect(isNavigationActive('/evaluations', '/evaluations', false)).toBe(true);
    expect(isNavigationActive('/evaluations/eval-456', '/evaluations', false)).toBe(true);
    expect(isNavigationActive('/evaluations/eval-456/report', '/evaluations', false)).toBe(true);
    expect(isNavigationActive('/syllabus-alignment', '/syllabus-alignment', false)).toBe(true);
    expect(isNavigationActive('/syllabus-alignment/doc-789', '/syllabus-alignment', false)).toBe(true);
    expect(isNavigationActive('/alignment', '/alignment', false)).toBe(true);
    expect(isNavigationActive('/alignment/check-1', '/alignment', false)).toBe(true);
    expect(isNavigationActive('/evaluation-map', '/evaluation-map', false)).toBe(true);
  });

  it('does not match unrelated routes with similar prefixes', () => {
    expect(isNavigationActive('/documents-archive', '/documents', false)).toBe(false);
    expect(isNavigationActive('/evaluations-old', '/evaluations', false)).toBe(false);
  });
});

describe('facultyNavGroups structure', () => {
  it('defines the required faculty grouped hierarchy', () => {
    expect(facultyNavGroups).toHaveLength(3);

    const [homeGroup, workspaceGroup, alignmentGroup] = facultyNavGroups;
    expect(homeGroup.id).toBe('home');
    expect(homeGroup.label).toBe('HOME');
    expect(homeGroup.items).toHaveLength(1);
    expect(homeGroup.items[0]).toMatchObject({ to: '/dashboard', label: 'Home', exact: true });

    expect(workspaceGroup.id).toBe('workspace');
    expect(workspaceGroup.label).toBe('WORKSPACE');
    expect(workspaceGroup.items).toHaveLength(2);
    expect(workspaceGroup.items[0]).toMatchObject({ to: '/documents', label: 'My SLMs', exact: false });
    expect(workspaceGroup.items[1]).toMatchObject({ to: '/evaluations', label: 'Evaluations', exact: false });

    expect(alignmentGroup.id).toBe('alignment');
    expect(alignmentGroup.label).toBe('ALIGNMENT');
    expect(alignmentGroup.items).toHaveLength(2);
    expect(alignmentGroup.items[0]).toMatchObject({
      to: '/syllabus-alignment',
      label: 'Syllabus Alignment',
      exact: false,
    });
    expect(alignmentGroup.items[1]).toMatchObject({
      to: '/alignment',
      label: 'Curriculum Check',
      exact: false,
    });
  });

  it('defines secondary Evaluation Map for faculty', () => {
    expect(facultySecondaryNavItems).toHaveLength(1);
    expect(facultySecondaryNavItems[0]).toMatchObject({
      to: '/evaluation-map',
      label: 'Evaluation Map',
      exact: false,
    });
  });

  it('preserves admin nav items unchanged', () => {
    const labels = adminNavItems.map((item) => item.label);
    expect(labels).toEqual([
      'Dashboard',
      'Users',
      'Ingest',
      'References',
      'Monitoring Matrix',
      'Knowledge Map',
      'Model Validation',
      'Prompts',
      'Logs',
    ]);
  });
});

describe('getRouteTitle', () => {
  it('returns Home for /dashboard', () => {
    expect(getRouteTitle('/dashboard')).toBe('Home');
  });

  it('returns My SLMs for /documents', () => {
    expect(getRouteTitle('/documents')).toBe('My SLMs');
  });

  it('returns Evaluation Interface for /documents/$documentId/evaluation', () => {
    expect(getRouteTitle('/documents/doc-1/evaluation')).toBe('Evaluation Interface');
  });

  it('returns Upload SLM for /upload', () => {
    expect(getRouteTitle('/upload')).toBe('Upload SLM');
  });

  it('returns Evaluations for /evaluations', () => {
    expect(getRouteTitle('/evaluations')).toBe('Evaluations');
  });

  it('returns Scorecard for /evaluations/$id', () => {
    expect(getRouteTitle('/evaluations/eval-1')).toBe('Scorecard');
  });

  it('returns Evaluation Map for faculty on /evaluation-map', () => {
    expect(getRouteTitle('/evaluation-map', 'faculty')).toBe('Evaluation Map');
  });

  it('returns Knowledge Map for admin on /evaluation-map', () => {
    expect(getRouteTitle('/evaluation-map', 'admin')).toBe('Knowledge Map');
  });

  it('returns Curriculum Check for /alignment', () => {
    expect(getRouteTitle('/alignment')).toBe('Curriculum Check');
  });
});
describe('getBreadcrumbs', () => {
  it('returns Faculty Workspace > Overview for /dashboard', () => {
    expect(getBreadcrumbs('/dashboard')).toEqual([
      { label: 'Faculty Workspace' },
      { label: 'Overview' },
    ]);
  });

  it('returns Faculty Workspace > My SLMs for /documents', () => {
    expect(getBreadcrumbs('/documents')).toEqual([
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'My SLMs' },
    ]);
  });

  it('returns My SLMs > Evaluation Setup for /documents/doc-123/evaluation', () => {
    expect(getBreadcrumbs('/documents/doc-123/evaluation')).toEqual([
      { label: 'My SLMs', to: '/documents' },
      { label: 'Evaluation Setup' },
    ]);
  });

  it('returns Administration > User Management for /admin/users', () => {
    expect(getBreadcrumbs('/admin/users')).toEqual([
      { label: 'Administration', to: '/admin' },
      { label: 'User Management' },
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
  it('returns not inert and not hidden on desktop regardless of mobileOpen', () => {
    expect(getSidebarInertState(false, false)).toEqual({ inert: false, ariaHidden: false });
    expect(getSidebarInertState(false, true)).toEqual({ inert: false, ariaHidden: false });
  });

  it('returns inert and aria-hidden on mobile when mobileOpen is false', () => {
    expect(getSidebarInertState(true, false)).toEqual({ inert: true, ariaHidden: true });
  });

  it('returns not inert and not aria-hidden on mobile when mobileOpen is true', () => {
    expect(getSidebarInertState(true, true)).toEqual({ inert: false, ariaHidden: false });
  });
});
