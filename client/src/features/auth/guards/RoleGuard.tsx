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
