import { describe, expect, it } from 'vitest';
import {
  facultyNavGroups,
  facultySecondaryNavItems,
  filterFacultyNavGroups,
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
    expect(isNavigationActive('/curriculum-alignment', '/curriculum-alignment', false)).toBe(true);
    expect(isNavigationActive('/curriculum-alignment/check-1', '/curriculum-alignment', false)).toBe(true);
    expect(isNavigationActive('/evaluation-map', '/evaluation-map', false)).toBe(true);
  });

  it('does not match unrelated routes with similar prefixes', () => {
    expect(isNavigationActive('/documents-archive', '/documents', false)).toBe(false);
    expect(isNavigationActive('/evaluations-old', '/evaluations', false)).toBe(false);
  });
});

describe('navigation group structure', () => {
  it('defines the required faculty grouped hierarchy', () => {
    expect(facultyNavGroups).toHaveLength(5);

    const [homeGroup, storageGroup, specialistsGroup, alignmentGroup, logsGroup] = facultyNavGroups;
    expect(homeGroup.id).toBe('home');
    expect(homeGroup.label).toBe('Home');
    expect(homeGroup.items).toHaveLength(1);
    expect(homeGroup.items[0]).toMatchObject({ to: '/dashboard', label: 'Overview', exact: true });

    expect(storageGroup.id).toBe('storage');
    expect(storageGroup.label).toBe('Documents');
    expect(storageGroup.items).toHaveLength(1);
    expect(storageGroup.items[0]).toMatchObject({ to: '/documents', label: 'Documents', exact: false });

    expect(specialistsGroup.id).toBe('specialists');
    expect(specialistsGroup.label).toBe('Evaluations');
    expect(specialistsGroup.items).toHaveLength(4);
    expect(specialistsGroup.items[0]).toMatchObject({ to: '/specialists/sme', label: 'SME', exact: false });
    expect(specialistsGroup.items[1]).toMatchObject({ to: '/specialists/coordinator', label: 'Coordinator', exact: false });
    expect(specialistsGroup.items[2]).toMatchObject({ to: '/specialists/gad', label: 'GAD', exact: false });
    expect(specialistsGroup.items[3]).toMatchObject({ to: '/specialists/itso', label: 'ITSO', exact: false });

    expect(alignmentGroup.id).toBe('alignment');
    expect(alignmentGroup.label).toBe('Alignment');
    expect(alignmentGroup.items).toHaveLength(2);
    expect(alignmentGroup.items[0]).toMatchObject({
      to: '/syllabus-alignment',
      label: 'Syllabus',
      exact: false,
    });
    expect(alignmentGroup.items[1]).toMatchObject({
      to: '/curriculum-alignment',
      label: 'Curriculum',
      exact: false,
    });

    expect(logsGroup.id).toBe('logs');
    expect(logsGroup.label).toBe('Logs');
    expect(logsGroup.items).toHaveLength(1);
    expect(logsGroup.items[0]).toMatchObject({
      to: '/evaluations',
      label: 'History',
      exact: true,
    });
  });

  it('leaves faculty secondary nav empty after moving Evaluation Map to admin', () => {
    expect(facultySecondaryNavItems).toHaveLength(0);
  });
});

describe('getRouteTitle', () => {
  it('returns Overview for /dashboard', () => {
    expect(getRouteTitle('/dashboard')).toBe('Overview');
  });

  it('returns Documents for /documents', () => {
    expect(getRouteTitle('/documents')).toBe('Documents');
  });

  it('returns Review for /documents/$documentId/evaluation (redirect)', () => {
    expect(getRouteTitle('/documents/doc-1/evaluation')).toBe('Review');
  });

  it('returns SME for /specialists/sme', () => {
    expect(getRouteTitle('/specialists/sme')).toBe('SME');
  });

  it('returns History for /evaluations', () => {
    expect(getRouteTitle('/evaluations')).toBe('History');
  });

  it('returns Scorecard for /evaluations/$id', () => {
    expect(getRouteTitle('/evaluations/eval-1')).toBe('Scorecard');
  });

  it('returns Syllabus for /syllabus-alignment', () => {
    expect(getRouteTitle('/syllabus-alignment')).toBe('Syllabus');
  });

  it('returns Curriculum for /curriculum-alignment', () => {
    expect(getRouteTitle('/curriculum-alignment')).toBe('Curriculum');
  });
});

describe('getBreadcrumbs', () => {
  it('returns Overview for /dashboard', () => {
    expect(getBreadcrumbs('/dashboard')).toEqual([
      { label: 'Overview' },
    ]);
  });

  it('returns Documents for /documents and /storage', () => {
    expect(getBreadcrumbs('/documents')).toEqual([
      { label: 'Documents' },
    ]);
    expect(getBreadcrumbs('/storage')).toEqual([
      { label: 'Documents' },
    ]);
  });

  it('returns Documents > Review for /documents/doc-123/evaluation', () => {
    expect(getBreadcrumbs('/documents/doc-123/evaluation')).toEqual([
      { label: 'Documents', to: '/documents' },
      { label: 'Review' },
    ]);
  });

  it('returns direct specialist breadcrumbs for specialist routes', () => {
    expect(getBreadcrumbs('/specialists/sme')).toEqual([
      { label: 'SME' },
    ]);
    expect(getBreadcrumbs('/specialists/sme/doc-1')).toEqual([
      { label: 'SME', to: '/specialists/sme' },
      { label: 'Scoreboard' },
    ]);
    expect(getBreadcrumbs('/specialists/gad')).toEqual([
      { label: 'GAD' },
    ]);
  });

  it('returns History breadcrumbs for evaluation routes', () => {
    expect(getBreadcrumbs('/evaluations')).toEqual([
      { label: 'History' },
    ]);
    expect(getBreadcrumbs('/evaluations/eval-1')).toEqual([
      { label: 'History', to: '/evaluations' },
      { label: 'Scorecard' },
    ]);
    expect(getBreadcrumbs('/evaluations/eval-1/report')).toEqual([
      { label: 'History', to: '/evaluations' },
      { label: 'Report' },
    ]);
  });

  it('returns Syllabus breadcrumbs for syllabus routes', () => {
    expect(getBreadcrumbs('/syllabus-alignment')).toEqual([
      { label: 'Syllabus' },
    ]);
    expect(getBreadcrumbs('/syllabus-alignment/doc-1')).toEqual([
      { label: 'Syllabus', to: '/syllabus-alignment' },
      { label: 'Workstation' },
    ]);
    expect(getBreadcrumbs('/syllabus-alignment/doc-1/report')).toEqual([
      { label: 'Syllabus', to: '/syllabus-alignment' },
      { label: 'Report' },
    ]);
  });

  it('returns Curriculum breadcrumbs for curriculum routes', () => {
    expect(getBreadcrumbs('/curriculum-alignment')).toEqual([
      { label: 'Curriculum' },
    ]);
    expect(getBreadcrumbs('/curriculum-alignment/check-1')).toEqual([
      { label: 'Curriculum', to: '/curriculum-alignment' },
      { label: 'Matrix' },
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

describe('filterFacultyNavGroups', () => {
  it('returns all groups unchanged when permissions are undefined or null', () => {
    expect(filterFacultyNavGroups(facultyNavGroups, undefined)).toEqual(facultyNavGroups);
    expect(filterFacultyNavGroups(facultyNavGroups, null)).toEqual(facultyNavGroups);
  });

  it('returns all groups unchanged when permissions array is empty (unrestricted)', () => {
    expect(filterFacultyNavGroups(facultyNavGroups, [])).toEqual(facultyNavGroups);
  });

  it('filters specialists to only assigned desks', () => {
    const result = filterFacultyNavGroups(facultyNavGroups, ['sme']);
    const specialistGroup = result.find((g) => g.id === 'specialists');
    expect(specialistGroup).toBeDefined();
    expect(specialistGroup?.items).toHaveLength(1);
    expect(specialistGroup?.items[0].to).toBe('/specialists/sme');
    expect(result.find((g) => g.id === 'logs')?.items).toHaveLength(1);
  });

  it('supports multiple specialist permissions', () => {
    const result = filterFacultyNavGroups(facultyNavGroups, ['coordinator', 'gad']);
    const specialistGroup = result.find((g) => g.id === 'specialists');
    expect(specialistGroup?.items).toHaveLength(2);
    expect(specialistGroup?.items.map((i) => i.to)).toEqual([
      '/specialists/coordinator',
      '/specialists/gad',
    ]);
  });
});
