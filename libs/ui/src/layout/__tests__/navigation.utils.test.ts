import { describe, it, expect } from 'vitest';
import {
  isNavigationActive,
  getAriaCurrent,
  getSidebarLayoutClasses,
  getSidebarInertState,
} from '../navigation.utils';

describe('navigation.utils in @equiped/ui', () => {
  describe('isNavigationActive', () => {
    it('matches exact paths when exact is true', () => {
      expect(isNavigationActive('/admin', '/admin', true)).toBe(true);
      expect(isNavigationActive('/admin/users', '/admin', true)).toBe(false);
    });

    it('matches sub-paths when exact is false', () => {
      expect(isNavigationActive('/admin/users', '/admin', false)).toBe(true);
      expect(isNavigationActive('/admin-other', '/admin', false)).toBe(false);
      expect(isNavigationActive('/admin', '/admin', false)).toBe(true);
    });
  });

  describe('getAriaCurrent', () => {
    it('returns "page" when active, otherwise undefined', () => {
      expect(getAriaCurrent(true)).toBe('page');
      expect(getAriaCurrent(false)).toBeUndefined();
    });
  });

  describe('getSidebarLayoutClasses', () => {
    it('returns collapsed layout offsets when isCollapsed is true', () => {
      const classes = getSidebarLayoutClasses(true);
      expect(classes.headerLeft).toBe('left-0 md:left-[4.5rem]');
      expect(classes.mainPadding).toBe('pl-0 md:pl-[4.5rem]');
      expect(classes.sidebarDesktopWidth).toBe('md:w-[4.5rem]');
    });

    it('returns expanded layout offsets when isCollapsed is false', () => {
      const classes = getSidebarLayoutClasses(false);
      expect(classes.headerLeft).toBe('left-0 md:left-64');
      expect(classes.mainPadding).toBe('pl-0 md:pl-64');
      expect(classes.sidebarDesktopWidth).toBe('md:w-64');
    });
  });

  describe('getSidebarInertState', () => {
    it('returns non-inert on desktop regardless of mobileOpen', () => {
      expect(getSidebarInertState(false, false)).toEqual({
        inert: false,
        ariaHidden: false,
      });
      expect(getSidebarInertState(false, true)).toEqual({
        inert: false,
        ariaHidden: false,
      });
    });

    it('returns inert when on mobile and closed', () => {
      expect(getSidebarInertState(true, false)).toEqual({
        inert: true,
        ariaHidden: true,
      });
    });

    it('returns non-inert when on mobile and open', () => {
      expect(getSidebarInertState(true, true)).toEqual({
        inert: false,
        ariaHidden: false,
      });
    });
  });
});
