import { redirect } from '@tanstack/react-router';
import type { AppRouterContext } from '../../../app/runtime';
import type { UserRole } from '../types';

export function requireRole(allowedRoles: readonly UserRole[], redirectTo = '/dashboard') {
  return ({ context }: { context: AppRouterContext }) => {
    const user = context.auth.user;

    if (!user || !allowedRoles.includes(user.role)) {
      throw redirect({ to: redirectTo });
    }
  };
}
