import { AppShell as BaseAppShell } from '@equiped/ui';
import { useAuth } from '@equiped/auth';
import { useLocation } from '@tanstack/react-router';
import {
  facultyNavGroups,
  facultySecondaryNavItems,
  filterFacultyNavGroups,
  getBreadcrumbs,
} from './navigation.utils';

export function AppShell() {
  const { user, logout } = useAuth();
  const pathname = useLocation({ select: (loc) => loc.pathname });
  const breadcrumbs = getBreadcrumbs(pathname);
  const navGroups = filterFacultyNavGroups(facultyNavGroups, user?.evaluatorPermissions);

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
      onLogout={logout}
      defaultInitials="EA"
      defaultUserName="EquipEd User"
      defaultUserEmail="No email available"
      userRole="faculty"
    />
  );
}
