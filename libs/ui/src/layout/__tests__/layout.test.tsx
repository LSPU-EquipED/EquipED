// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React from 'react';
import { AppShell } from '../AppShell';
import { Sidebar } from '../Sidebar';
import { SquaresFour, Users } from '@phosphor-icons/react';
import type { NavGroup } from '../navigation.types';

let mockPathname = '/dashboard';

vi.mock('@tanstack/react-router', () => ({
  useLocation: ({ select }: { select?: (loc: { pathname: string }) => string }) => {
    return select ? select({ pathname: mockPathname }) : { pathname: mockPathname };
  },
  Link: ({
    to,
    children,
    className,
    onClick,
    activeOptions: _activeOptions,
    ...props
  }: {
    to: string;
    children?: React.ReactNode;
    className?: string;
    onClick?: () => void;
    activeOptions?: unknown;
  }) => (
    <a href={to} className={className} onClick={onClick} {...props}>
      {children}
    </a>
  ),
  Outlet: () => <div data-testid="test-outlet">Outlet content</div>,
}));

describe('Layout primitives: Sidebar and AppShell', () => {
  const sampleNavGroups: readonly NavGroup[] = [
    {
      id: 'main',
      label: 'Main',
      items: [
        { to: '/dashboard', label: 'Overview', icon: SquaresFour, exact: true },
        { to: '/users', label: 'Users', icon: Users, exact: false },
      ],
    },
  ];

  beforeEach(() => {
    cleanup();
    mockPathname = '/dashboard';
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  describe('Sidebar', () => {
    it('renders navigation groups, items, and brand title', () => {
      render(
        <Sidebar
          collapsed={false}
          onToggle={vi.fn()}
          navGroups={sampleNavGroups}
          brandTitle="EquipED"
          brandSubtitle="LSPU"
        />,
      );

      expect(screen.getByText('EquipED')).toBeDefined();
      expect(screen.getByText('Overview')).toBeDefined();
      expect(screen.getByText('Users')).toBeDefined();
    });

    it('highlights active item and sets aria-current="page"', () => {
      mockPathname = '/dashboard';
      render(
        <Sidebar
          collapsed={false}
          onToggle={vi.fn()}
          navGroups={sampleNavGroups}
        />,
      );

      const overviewLink = screen.getByText('Overview').closest('a');
      expect(overviewLink?.getAttribute('aria-current')).toBe('page');
      expect(overviewLink?.className).toContain('text-primary');

      const usersLink = screen.getByText('Users').closest('a');
      expect(usersLink?.getAttribute('aria-current')).toBeNull();
    });

    it('calls onToggle when collapse toggle button is clicked', () => {
      const onToggle = vi.fn();
      render(
        <Sidebar
          collapsed={false}
          onToggle={onToggle}
          navGroups={sampleNavGroups}
        />,
      );

      const toggleButton = screen.getByRole('button', { name: /collapse sidebar/i });
      fireEvent.click(toggleButton);
      expect(onToggle).toHaveBeenCalledTimes(1);
    });

    it('calls onNavigate when nav link is clicked', () => {
      const onNavigate = vi.fn();
      render(
        <Sidebar
          collapsed={false}
          onToggle={vi.fn()}
          onNavigate={onNavigate}
          navGroups={sampleNavGroups}
        />,
      );

      const usersLink = screen.getByText('Users');
      fireEvent.click(usersLink);
      expect(onNavigate).toHaveBeenCalledTimes(1);
    });
  });

  describe('AppShell', () => {
    it('renders top bar, breadcrumbs, user initials, and outlet', () => {
      const onLogout = vi.fn();
      render(
        <AppShell
          homeRoute="/dashboard"
          homeLabel="Home"
          navGroups={sampleNavGroups}
          breadcrumbs={[{ label: 'Users' }]}
          user={{ displayName: 'Juan Dela Cruz', email: 'juan@lspu.edu.ph', role: 'faculty' }}
          onLogout={onLogout}
        />,
      );

      expect(screen.getAllByText('Users')).toHaveLength(2);
      expect(screen.getByTestId('test-outlet')).toBeDefined();
      expect(screen.getByText('JD')).toBeDefined();
    });

    it('opens account menu on click and handles logout', async () => {
      const onLogout = vi.fn();
      render(
        <AppShell
          homeRoute="/dashboard"
          homeLabel="Home"
          navGroups={sampleNavGroups}
          breadcrumbs={[]}
          user={{ displayName: 'Admin User', email: 'admin@lspu.edu.ph', role: 'admin' }}
          onLogout={onLogout}
        />,
      );

      const accountBtn = screen.getByRole('button', { name: /user account menu/i });
      fireEvent.click(accountBtn);

      expect(screen.getByText('Admin User')).toBeDefined();
      expect(screen.getByText('admin@lspu.edu.ph')).toBeDefined();

      const logoutBtn = screen.getByRole('menuitem', { name: /sign out/i });
      fireEvent.click(logoutBtn);
      expect(onLogout).toHaveBeenCalledTimes(1);
    });

    it('closes account menu on Escape key press', () => {
      render(
        <AppShell
          homeRoute="/dashboard"
          homeLabel="Home"
          navGroups={sampleNavGroups}
          breadcrumbs={[]}
          user={{ displayName: 'Admin User', email: 'admin@lspu.edu.ph', role: 'admin' }}
          onLogout={vi.fn()}
        />,
      );

      const accountBtn = screen.getByRole('button', { name: /user account menu/i });
      fireEvent.click(accountBtn);
      expect(screen.getByText('admin@lspu.edu.ph')).toBeDefined();

      fireEvent.keyDown(document, { key: 'Escape' });
      expect(screen.queryByText('admin@lspu.edu.ph')).toBeNull();
    });
  });
});
