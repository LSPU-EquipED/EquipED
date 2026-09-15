// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import type { AdminUserResponse } from '../../types';
import { UserManagementPage } from '../UserManagementPage';

const mockSetUserApprovalMutate = vi.fn();
const mockDeactivateUserMutate = vi.fn();
const mockHardDeleteUserMutate = vi.fn();

const mockUsers: AdminUserResponse[] = [
  {
    user_id: 'user-pending-1',
    name: 'Pending Faculty',
    email: 'pending@lspu.edu.ph',
    role: 'faculty',
    is_active: false,
    account_status: 'pending',
    created_at: '2026-08-01T08:00:00Z',
  },
  {
    user_id: 'user-approved-1',
    name: 'Active Approved Faculty',
    email: 'active@lspu.edu.ph',
    role: 'faculty',
    is_active: true,
    account_status: 'approved',
    created_at: '2026-08-02T08:00:00Z',
  },
  {
    user_id: 'user-suspended-1',
    name: 'Suspended Faculty',
    email: 'suspended@lspu.edu.ph',
    role: 'faculty',
    is_active: false,
    account_status: 'suspended',
    created_at: '2026-08-03T08:00:00Z',
  },
  {
    user_id: 'user-rejected-1',
    name: 'Rejected Faculty',
    email: 'rejected@lspu.edu.ph',
    role: 'faculty',
    is_active: false,
    account_status: 'rejected',
    created_at: '2026-08-04T08:00:00Z',
  },
];

vi.mock('../../hooks/useAdminUsers', () => ({
  useAdminUsers: () => ({
    data: { items: mockUsers, total: mockUsers.length },
    isLoading: false,
    isError: false,
  }),
  useCreateUser: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateUser: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useDeactivateUser: () => ({
    mutate: mockDeactivateUserMutate,
    isPending: false,
  }),
  useHardDeleteUser: () => ({
    mutate: mockHardDeleteUserMutate,
    isPending: false,
  }),
  useSetUserApproval: () => ({
    mutate: mockSetUserApprovalMutate,
    isPending: false,
  }),
}));

describe('UserManagementPage', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockImplementation(() => true);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders explicit Suspended badge for suspended account status', () => {
    render(<UserManagementPage />);

    expect(screen.getByText('Suspended')).toBeDefined();
    expect(screen.getByText('Pending approval')).toBeDefined();
    expect(screen.getByText('Active')).toBeDefined();
    expect(screen.getByText('Rejected')).toBeDefined();
  });

  it('renders Suspend action for approved active user and calls setApproval with suspended after confirmation', () => {
    render(<UserManagementPage />);

    const suspendBtn = screen.getByRole('button', { name: 'Suspend Active Approved Faculty' });
    expect(suspendBtn).toBeDefined();

    fireEvent.click(suspendBtn);

    expect(window.confirm).toHaveBeenCalledWith(
      'Suspend Active Approved Faculty? This will suspend the account. You can reapprove it later.',
    );
    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-approved-1',
      accountStatus: 'suspended',
    });
    expect(mockDeactivateUserMutate).not.toHaveBeenCalled();
  });

  it('does not trigger suspension if confirmation is declined', () => {
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false);
    render(<UserManagementPage />);

    const suspendBtn = screen.getByRole('button', { name: 'Suspend Active Approved Faculty' });
    fireEvent.click(suspendBtn);

    expect(mockSetUserApprovalMutate).not.toHaveBeenCalled();
  });

  it('renders Reapprove action for suspended user and calls setApproval with approved', () => {
    render(<UserManagementPage />);

    const reapproveBtn = screen.getByRole('button', { name: 'Reapprove Suspended Faculty' });
    expect(reapproveBtn).toBeDefined();

    fireEvent.click(reapproveBtn);

    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-suspended-1',
      accountStatus: 'approved',
    });
  });

  it('renders Approve and Reject actions for pending user', () => {
    render(<UserManagementPage />);

    const approveBtn = screen.getByRole('button', { name: 'Approve Pending Faculty' });
    const rejectBtn = screen.getByRole('button', { name: 'Reject Pending Faculty' });

    expect(approveBtn).toBeDefined();
    expect(rejectBtn).toBeDefined();

    fireEvent.click(approveBtn);
    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-pending-1',
      accountStatus: 'approved',
    });

    fireEvent.click(rejectBtn);
    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-pending-1',
      accountStatus: 'rejected',
    });
  });

  it('renders Approve action for rejected user', () => {
    render(<UserManagementPage />);

    const approveBtn = screen.getByRole('button', { name: 'Approve Rejected Faculty' });
    expect(approveBtn).toBeDefined();

    fireEvent.click(approveBtn);
    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-rejected-1',
      accountStatus: 'approved',
    });
  });
});
