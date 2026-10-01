// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import React from 'react';
import type { AdminUserResponse } from '../../types';
import { UserManagementPage } from '../UserManagementPage';

const mockSetUserApprovalMutate = vi.fn();
const mockDeactivateUserMutate = vi.fn();
const mockHardDeleteUserMutate = vi.fn();

const currentAdmin = { id: 'admin-current', displayName: 'Signed-in Admin', email: 'self@lspu.edu.ph', role: 'admin' };
vi.mock('@equiped/auth', () => ({ useAuth: () => ({ user: currentAdmin }) }));

const mockUsers: AdminUserResponse[] = [
  {
    user_id: 'admin-current', name: 'Signed-in Admin', email: 'self@lspu.edu.ph',
    role: 'admin', is_active: true, account_status: 'approved', created_at: '2026-08-01T08:00:00Z',
  },
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

  it('hides the signed-in administrator from the directory, search, and bulk selection', () => {
    render(<UserManagementPage />);
    expect(screen.queryByText('Signed-in Admin')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Actions for Signed-in Admin' })).toBeNull();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all users' }));
    expect(screen.getByRole('button', { name: 'Deactivate (4)' })).toBeDefined();
    fireEvent.change(screen.getByRole('textbox', { name: 'Search users' }), { target: { value: 'self@lspu.edu.ph' } });
    expect(screen.getByText('No users match your filters')).toBeDefined();
  });

  it('keeps row commands hidden until the three-dot menu is opened', () => {
    render(<UserManagementPage />);
    expect(screen.queryByRole('menuitem')).toBeNull();
    const trigger = screen.getByRole('button', { name: 'Actions for Pending Faculty' });
    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('menuitem', { name: 'Edit' })).toBeDefined();
    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('resets typed deletion confirmation when cancelled and another account is selected', () => {
    render(<UserManagementPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Actions for Active Approved Faculty' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Confirm account email' }), { target: { value: 'active@lspu.edu.ph' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    fireEvent.click(screen.getByRole('button', { name: 'Actions for Pending Faculty' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
    expect((screen.getByRole('textbox', { name: 'Confirm account email' }) as HTMLInputElement).value).toBe('');
    expect(screen.getByRole('button', { name: 'Delete' }).hasAttribute('disabled')).toBe(true);
    expect(mockHardDeleteUserMutate).not.toHaveBeenCalled();
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

    fireEvent.click(screen.getByRole('button', { name: 'Actions for Active Approved Faculty' }));
    const suspendBtn = screen.getByRole('menuitem', { name: 'Suspend' });
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

    fireEvent.click(screen.getByRole('button', { name: 'Actions for Active Approved Faculty' }));
    const suspendBtn = screen.getByRole('menuitem', { name: 'Suspend' });
    fireEvent.click(suspendBtn);

    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);

    expect(mockSetUserApprovalMutate).not.toHaveBeenCalled();
  });

  it('opens Delete confirmation modal and calls hardDeleteUser upon confirmation', () => {
    render(<UserManagementPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Actions for Active Approved Faculty' }));
    const deleteBtn = screen.getByRole('menuitem', { name: 'Delete' });
    fireEvent.click(deleteBtn);

    const dialog = screen.getByRole('dialog', { name: 'Delete Active Approved Faculty?' });
    expect(dialog).toBeDefined();

    const confirmBtn = screen.getByRole('button', { name: 'Delete' });
    expect(confirmBtn.hasAttribute('disabled')).toBe(true);
    fireEvent.click(confirmBtn);
    fireEvent.submit(dialog.querySelector('form')!);
    expect(mockHardDeleteUserMutate).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole('textbox', { name: 'Confirm account email' }), { target: { value: 'wrong@lspu.edu.ph' } });
    expect(confirmBtn.hasAttribute('disabled')).toBe(true);
    fireEvent.change(screen.getByRole('textbox', { name: 'Confirm account email' }), { target: { value: 'active@lspu.edu.ph' } });
    expect(confirmBtn.hasAttribute('disabled')).toBe(false);
    fireEvent.click(confirmBtn);

    expect(mockHardDeleteUserMutate).toHaveBeenCalledWith('user-approved-1');
  });

  it('renders Reapprove action for suspended user and calls setApproval with approved', () => {
    render(<UserManagementPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Actions for Suspended Faculty' }));
    const reapproveBtn = screen.getByRole('menuitem', { name: 'Reapprove' });
    expect(reapproveBtn).toBeDefined();

    fireEvent.click(reapproveBtn);

    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-suspended-1',
      accountStatus: 'approved',
    });
  });

  it('renders Approve and Reject actions for pending user', () => {
    render(<UserManagementPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Actions for Pending Faculty' }));
    const approveBtn = screen.getByRole('menuitem', { name: 'Approve' });
    const rejectBtn = screen.getByRole('menuitem', { name: 'Reject' });

    expect(approveBtn).toBeDefined();
    expect(rejectBtn).toBeDefined();

    fireEvent.click(approveBtn);
    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-pending-1',
      accountStatus: 'approved',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Actions for Pending Faculty' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Reject' }));
    expect(mockSetUserApprovalMutate).toHaveBeenCalledWith({
      userId: 'user-pending-1',
      accountStatus: 'rejected',
    });
  });

  it('renders Approve action for rejected user', () => {
    render(<UserManagementPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Actions for Rejected Faculty' }));
    const approveBtn = screen.getByRole('menuitem', { name: 'Approve' });
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
