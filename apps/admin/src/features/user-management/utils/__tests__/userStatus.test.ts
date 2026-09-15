import { describe, expect, it } from 'vitest';
import { getUserStatusBadge } from '../userStatus';

describe('getUserStatusBadge', () => {
  it('returns pending warning badge for pending account_status', () => {
    const badge = getUserStatusBadge({ account_status: 'pending', is_active: false });
    expect(badge).toEqual({ label: 'Pending approval', variant: 'warning' });
  });

  it('returns rejected destructive badge for rejected account_status', () => {
    const badge = getUserStatusBadge({ account_status: 'rejected', is_active: false });
    expect(badge).toEqual({ label: 'Rejected', variant: 'destructive' });
  });

  it('renders explicit Suspended destructive badge when account_status is suspended', () => {
    const suspendedInactive = getUserStatusBadge({ account_status: 'suspended', is_active: false });
    expect(suspendedInactive).toEqual({ label: 'Suspended', variant: 'destructive' });

    const suspendedActiveFlag = getUserStatusBadge({
      account_status: 'suspended',
      is_active: true,
    });
    expect(suspendedActiveFlag).toEqual({ label: 'Suspended', variant: 'destructive' });
  });

  it('returns Active success badge for approved active account', () => {
    const badge = getUserStatusBadge({ account_status: 'approved', is_active: true });
    expect(badge).toEqual({ label: 'Active', variant: 'success' });
  });

  it('returns Inactive neutral badge for approved inactive account', () => {
    const badge = getUserStatusBadge({ account_status: 'approved', is_active: false });
    expect(badge).toEqual({ label: 'Inactive', variant: 'neutral' });
  });
});
