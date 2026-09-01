import type { StatusVariant } from '@/shared/constants/theme';
import type { AdminUserResponse } from '../types';

export function getUserStatusBadge(user: Pick<AdminUserResponse, 'account_status' | 'is_active'>): {
  label: string;
  variant: StatusVariant;
} {
  if (user.account_status === 'pending') {
    return { label: 'Pending approval', variant: 'warning' };
  }
  if (user.account_status === 'rejected') {
    return { label: 'Rejected', variant: 'destructive' };
  }
  if (user.account_status === 'suspended') {
    return { label: 'Suspended', variant: 'destructive' };
  }
  if (user.account_status === 'approved') {
    return user.is_active
      ? { label: 'Active', variant: 'success' }
      : { label: 'Inactive', variant: 'neutral' };
  }
  return user.is_active
    ? { label: 'Active', variant: 'success' }
    : { label: 'Inactive', variant: 'neutral' };
}
