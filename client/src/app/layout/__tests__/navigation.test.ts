import { describe, expect, it } from 'vitest';
import {
  adminNavGroups,
  facultyNavGroups,
  facultySecondaryNavItems,
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

describe('navigation group structure', () => {
  it('defines the required faculty grouped hierarchy', () => {
    expect(facultyNavGroups).toHaveLength(4);

    const [homeGroup, storageGroup, specialistsGroup, alignmentGroup] = facultyNavGroups;
    expect(homeGroup.id).toBe('home');
    expect(homeGroup.label).toBe('HOME');
    expect(homeGroup.items).toHaveLength(1);
    expect(homeGroup.items[0]).toMatchObject({ to: '/dashboard', label: 'Home', exact: true });

    expect(storageGroup.id).toBe('storage');
    expect(storageGroup.label).toBe('SLM REPOSITORY');
    expect(storageGroup.items).toHaveLength(1);
    expect(storageGroup.items[0]).toMatchObject({ to: '/documents', label: 'SLM Storage', exact: false });

    expect(specialistsGroup.id).toBe('specialists');
    expect(specialistsGroup.label).toBe('EVALUATION SPECIALISTS');
    expect(specialistsGroup.items).toHaveLength(4);
    expect(specialistsGroup.items[0]).toMatchObject({ to: '/specialists/sme', label: 'Subject Matter Expert', exact: false });
    expect(specialistsGroup.items[1]).toMatchObject({ to: '/specialists/coordinator', label: 'Program Coordinator', exact: false });
    expect(specialistsGroup.items[2]).toMatchObject({ to: '/specialists/gad', label: 'Gender & Development', exact: false });
    expect(specialistsGroup.items[3]).toMatchObject({ to: '/specialists/itso', label: 'Innovation & IP (ITSO)', exact: false });

    expect(alignmentGroup.id).toBe('alignment');
    expect(alignmentGroup.label).toBe('ALIGNMENT & AUDIT');
    expect(alignmentGroup.items).toHaveLength(3);
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
    expect(alignmentGroup.items[2]).toMatchObject({
      to: '/evaluations',
      label: 'Evaluation History',
      exact: true,
    });
  });
  it('leaves faculty secondary nav empty after moving Evaluation Map to admin', () => {
    expect(facultySecondaryNavItems).toHaveLength(0);
  });

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
  it('returns Home for /dashboard', () => {
    expect(getRouteTitle('/dashboard')).toBe('Home');
  });

  it('returns My SLMs for /documents', () => {
    expect(getRouteTitle('/documents')).toBe('My SLMs');
  });

  it('returns Specialist Review for /documents/$documentId/evaluation (redirect)', () => {
    expect(getRouteTitle('/documents/doc-1/evaluation')).toBe('Specialist Review');
  });

  it('returns Upload SLM for /upload', () => {
    expect(getRouteTitle('/upload')).toBe('Upload SLM');
  });

  it('returns Evaluation History for /evaluations', () => {
    expect(getRouteTitle('/evaluations')).toBe('Evaluation History');
  });

  it('returns Scorecard for /evaluations/$id', () => {
    expect(getRouteTitle('/evaluations/eval-1')).toBe('Scorecard');
  });

  it('returns Knowledge Map for /evaluation-map', () => {
    expect(getRouteTitle('/evaluation-map')).toBe('Knowledge Map');
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

  it('returns Faculty Workspace > SLM Storage for /documents and /storage', () => {
    expect(getBreadcrumbs('/documents')).toEqual([
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'SLM Storage' },
    ]);
    expect(getBreadcrumbs('/storage')).toEqual([
      { label: 'Faculty Workspace', to: '/dashboard' },
      { label: 'SLM Storage' },
    ]);
  });

  it('returns Specialists breadcrumbs for specialist routes', () => {
    expect(getBreadcrumbs('/specialists/sme')).toEqual([
      { label: 'Specialists', to: '/dashboard' },
      { label: 'Subject Matter Expert' },
    ]);
    expect(getBreadcrumbs('/specialists/gad')).toEqual([
      { label: 'Specialists', to: '/dashboard' },
      { label: 'Gender & Development' },
    ]);
  });

  it('returns SLM Storage > Specialist Review for /documents/doc-123/evaluation (redirect)', () => {
    expect(getBreadcrumbs('/documents/doc-123/evaluation')).toEqual([
      { label: 'SLM Storage', to: '/documents' },
      { label: 'Specialist Review' },
    ]);
  });

  it('returns Administration > User Management for /admin/users', () => {
    expect(getBreadcrumbs('/admin/users')).toEqual([
      { label: 'Administration', to: '/admin' },
      { label: 'User Management' },
    ]);
  });

  it('returns Administration > Agent Prompts for /admin/prompts', () => {
    expect(getBreadcrumbs('/admin/prompts')).toEqual([
      { label: 'Administration', to: '/admin' },
      { label: 'Agent Prompts' },
    ]);
  });

  it('returns Administration > Agent Prompts for /admin/prompts/coordinator', () => {
    expect(getBreadcrumbs('/admin/prompts/coordinator')).toEqual([
      { label: 'Administration', to: '/admin' },
      { label: 'Agent Prompts' },
    ]);
  });

  it('returns Administration > Agent Prompts for /admin/prompts/sme', () => {
    expect(getBreadcrumbs('/admin/prompts/sme')).toEqual([
      { label: 'Administration', to: '/admin' },
      { label: 'Agent Prompts' },
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
