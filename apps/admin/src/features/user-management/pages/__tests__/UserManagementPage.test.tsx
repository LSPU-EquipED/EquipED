// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
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
    mutateAsync: mockDeactivateUserMutate,
    isPending: false,
  }),
  useHardDeleteUser: () => ({
    mutate: mockHardDeleteUserMutate,
    mutateAsync: mockHardDeleteUserMutate,
    isPending: false,
  }),
  useSetUserApproval: () => ({
    mutate: mockSetUserApprovalMutate,
    mutateAsync: mockSetUserApprovalMutate,
    isPending: false,
  }),
}));

describe('UserManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

    const dialog = screen.getByRole('dialog', { name: 'Suspend Active Approved Faculty?' });
    expect(dialog).toBeDefined();

    const confirmBtn = screen.getByRole('button', { name: 'Suspend' });
    fireEvent.click(confirmBtn);

    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-approved-1',
      accountStatus: 'suspended',
    });
    expect(mockDeactivateUserMutate).not.toHaveBeenCalled();
  });

  it('does not trigger suspension if confirmation is declined', () => {
    render(<UserManagementPage />);

    const suspendBtn = screen.getByRole('button', { name: 'Suspend Active Approved Faculty' });
    fireEvent.click(suspendBtn);

    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);

    expect(mockSetUserApprovalMutate).not.toHaveBeenCalled();
  });

  it('opens Delete confirmation modal and calls hardDeleteUser upon confirmation', () => {
    render(<UserManagementPage />);

    const deleteBtn = screen.getByRole('button', { name: 'Delete Active Approved Faculty' });
    fireEvent.click(deleteBtn);

    const dialog = screen.getByRole('dialog', { name: 'Delete Active Approved Faculty?' });
    expect(dialog).toBeDefined();

    const confirmBtn = screen.getByRole('button', { name: 'Delete' });
    fireEvent.click(confirmBtn);

    expect(mockHardDeleteUserMutate).toHaveBeenCalledWith('user-approved-1');
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

  it('prevents duplicate submission and closing during an in-flight batch, then retries only remaining users', async () => {
    // Fail on user-approved-1 on first call, then succeed on retry
    let callCount = 0;
    let releaseFirst!: () => void;
    mockDeactivateUserMutate.mockImplementation(async (userId: string) => {
      callCount += 1;
      if (callCount === 1) await new Promise<void>((resolve) => { releaseFirst = resolve; });
      if (userId === 'user-approved-1' && callCount === 2) {
        throw new Error('Failed to deactivate user-approved-1');
      }
      return { success: true };
    });

    render(<UserManagementPage />);

    // Select user-pending-1 and user-approved-1
    const pendingCheckbox = screen.getByRole('checkbox', { name: 'Select Pending Faculty' });
    const approvedCheckbox = screen.getByRole('checkbox', { name: 'Select Active Approved Faculty' });
    fireEvent.click(pendingCheckbox);
    fireEvent.click(approvedCheckbox);

    // Click bulk deactivate button
    const bulkButton = screen.getByRole('button', { name: 'Deactivate (2)' });
    fireEvent.click(bulkButton);

    // Modal opens
    const dialog = screen.getByRole('dialog', { name: 'Deactivate 2 user(s)?' });
    expect(dialog).toBeDefined();
    const modalConfirmBtn = within(dialog).getByRole('button', { name: 'Deactivate (2)' });
    expect(screen.getByText('Deactivate 2 user(s)? This will deactivate their accounts. You can re-activate them later.')).toBeDefined();

    // Confirm bulk deactivate
    fireEvent.click(modalConfirmBtn);
    fireEvent.click(modalConfirmBtn);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(mockDeactivateUserMutate).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('dialog', { name: 'Deactivate 2 user(s)?' })).toBeDefined();

    await act(async () => { releaseFirst(); });
    // 1st succeeded (user-pending-1), 2nd failed (user-approved-1)
    expect(mockDeactivateUserMutate).toHaveBeenCalledWith('user-pending-1');
    expect(mockDeactivateUserMutate).toHaveBeenCalledWith('user-approved-1');

    // Error is shown in modal, modal stays open, remaining users reported accurately
    expect(screen.getByText('Failed to deactivate user-approved-1')).toBeDefined();
    const updatedDialog = screen.getByRole('dialog', { name: 'Deactivate 1 user(s)?' });
    expect(updatedDialog).toBeDefined();
    const retryBtn = within(updatedDialog).getByRole('button', { name: 'Deactivate (1)' });
    expect(screen.getByText('Deactivate 1 user(s)? This will deactivate their accounts. You can re-activate them later.')).toBeDefined();

    // Now retry: clicking confirm again with the 1 remaining user
    await act(async () => {
      fireEvent.click(retryBtn);
    });

    // mutate called 3 times in total (1 for user-pending-1, 2 for user-approved-1)
    expect(mockDeactivateUserMutate).toHaveBeenCalledTimes(3);

    // The operation completed: the selection and confirmation modal are cleared.
    expect(screen.queryByRole('dialog', { name: /Deactivate/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /Deactivate \(/ })).toBeNull();
  });
});
