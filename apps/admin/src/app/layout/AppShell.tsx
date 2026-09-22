import { AppShell as BaseAppShell } from '@equiped/ui';
import { useAuth, navigateCrossApp } from '@equiped/auth';
import { useLocation } from '@tanstack/react-router';
import { adminNavGroups, getBreadcrumbs } from './navigation.utils';

export function AppShell() {
  const { user, logout } = useAuth();
  const pathname = useLocation({ select: (loc) => loc.pathname });
  const breadcrumbs = getBreadcrumbs(pathname);

  const handleLogout = async () => {
    await logout();
    navigateCrossApp('/login');
  };

  return (
    <BaseAppShell
      homeRoute="/admin"
      homeLabel="Admin Dashboard"
      brandSubtitle="LSPU Admin"
      brandTitle="EquipED"
      navGroups={adminNavGroups}
      breadcrumbs={breadcrumbs}
      user={user}
      onLogout={handleLogout}
      defaultInitials="AD"
      defaultUserName="Admin User"
      defaultUserEmail="admin@lspu.edu.ph"
      userRole="admin"
    />
  );
}
