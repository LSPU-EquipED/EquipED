import { redirect } from '@tanstack/react-router';
import type { AppRouterContext } from '../../../app/runtime';
import type { UserRole } from '../types';

export function requireRole(
  allowedRoles: readonly UserRole[],
  unauthenticatedRedirectTo = '/login',
  unauthorizedRedirectTo?: string,
) {
  return ({ context }: { context: AppRouterContext }) => {
    const user = context.auth.user;

    if (!user || context.auth.status !== 'authenticated') {
      throw redirect({ to: unauthenticatedRedirectTo });
    }

    if (!allowedRoles.includes(user.role)) {
      const fallback = user.role === 'admin' ? '/admin' : '/dashboard';
      throw redirect({ to: unauthorizedRedirectTo ?? fallback });
    }
  };
}

export function requireEvaluatorPermission(
  getAgentId: (params: Record<string, string>) => string,
  unauthorizedRedirectTo = '/dashboard',
) {
  return ({ context, params }: { context: AppRouterContext; params: Record<string, string> }) => {
    const user = context.auth.user;

    if (!user || context.auth.status !== 'authenticated') {
      throw redirect({ to: '/login' });
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
      throw redirect({ to: unauthorizedRedirectTo });
    }
  };
}
