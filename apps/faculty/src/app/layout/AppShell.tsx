import { useEffect } from 'react';
import { AppShell as BaseAppShell } from '@equiped/ui';
import { useAuth } from '@equiped/auth';
import { useLocation, useNavigate } from '@tanstack/react-router';
import {
  facultyNavGroups,
  facultySecondaryNavItems,
  filterFacultyNavGroups,
  getBreadcrumbs,
} from './navigation.utils';

export function AppShell() {
  const { user, logout, status } = useAuth();
  const navigate = useNavigate();
  const pathname = useLocation({ select: (loc) => loc.pathname });
  const breadcrumbs = getBreadcrumbs(pathname);
  const navGroups = filterFacultyNavGroups(facultyNavGroups, user?.evaluatorPermissions);

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      void navigate({ to: '/login' });
    }
  };

  useEffect(() => {
    if (status === 'anonymous') {
      void navigate({ to: '/login' });
    }
  }, [status, navigate]);

  return (
    <BaseAppShell
      homeRoute="/dashboard"
      homeLabel="Home"
      brandSubtitle="LSPU"
      brandTitle="EquipED"
      navGroups={navGroups}
      secondaryNavItems={facultySecondaryNavItems}
      breadcrumbs={breadcrumbs}
      user={user}
      onLogout={handleLogout}
      defaultInitials="EA"
      defaultUserName="EquipEd User"
      defaultUserEmail="No email available"
      userRole="faculty"
    />
  );
}
