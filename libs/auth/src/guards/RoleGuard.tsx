import { redirect } from '@tanstack/react-router';
import { getCrossAppUrl, navigateCrossApp } from '../navigation';
import type { AppAuthUser, UserRole } from '../types';

export type AuthRouterContext = {
  auth: {
    user: AppAuthUser | null;
    status: 'anonymous' | 'authenticated';
  };
};

export function requireRole(
  allowedRoles: readonly UserRole[],
  unauthenticatedRedirectTo = '/login',
  unauthorizedRedirectTo?: string,
) {
  return ({ context }: { context: AuthRouterContext }) => {
    const user = context.auth.user;

    if (!user || context.auth.status !== 'authenticated') {
      throw redirect({ to: unauthenticatedRedirectTo as any });
    }

    if (!allowedRoles.includes(user.role)) {
      if (user.role === 'admin') {
        const dest = unauthorizedRedirectTo ?? '/admin';
        navigateCrossApp(dest);
        throw redirect({ href: getCrossAppUrl(dest) as any });
      }
      throw redirect({ to: (unauthorizedRedirectTo ?? '/dashboard') as any });
    }
  };
}

export function requireEvaluatorPermission(
  getAgentId: (params: Record<string, string>) => string,
  unauthorizedRedirectTo = '/dashboard',
) {
  return ({ context, params }: { context: AuthRouterContext; params: Record<string, string> }) => {
    const user = context.auth.user;

    if (!user || context.auth.status !== 'authenticated') {
      throw redirect({ to: '/login' as any });
    }

    if (user.role === 'admin') {
      return;
    }

    if (
      user.evaluatorPermissions === undefined ||
      user.evaluatorPermissions === null ||
      user.evaluatorPermissions.length === 0
    ) {
      return;
    }

    const agentId = getAgentId(params);
    if (!user.evaluatorPermissions.includes(agentId)) {
      throw redirect({ to: unauthorizedRedirectTo as any });
    }
  };
}
