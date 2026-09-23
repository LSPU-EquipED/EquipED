import { useState, useMemo, useRef } from 'react';
import { MagnifyingGlass, Plus, UserMinus } from '@phosphor-icons/react';
import { Button, ConfirmationModal, PageContainer } from '@equiped/ui';
import { CreateUserModal } from '../components/CreateUserModal';
import { EditUserModal } from '../components/EditUserModal';
import { UserFiltersToolbar, type RoleFilter, type StatusFilter } from '../components/UserFiltersToolbar';
import { UserTable } from '../components/UserTable';
import {
  useAdminUsers,
  useDeactivateUser,
  useHardDeleteUser,
  useSetUserApproval,
} from '../hooks/useAdminUsers';
import type { AdminUserResponse, UserCounts } from '../types';

export function UserManagementPage() {
  const { data, isLoading, isError } = useAdminUsers();
  const deactivateUser = useDeactivateUser();
  const hardDeleteUser = useHardDeleteUser();
  const setApproval = useSetUserApproval();

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<AdminUserResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Confirmation modal states
  const [userToSuspend, setUserToSuspend] = useState<AdminUserResponse | null>(null);
  const [userToDelete, setUserToDelete] = useState<AdminUserResponse | null>(null);
  const [isBulkDeactivateOpen, setIsBulkDeactivateOpen] = useState(false);

  // Modal error states
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [suspendError, setSuspendError] = useState<string | null>(null);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const bulkDeactivationLock = useRef(false);
  const [isBulkDeactivationRunning, setIsBulkDeactivationRunning] = useState(false);

  const items = useMemo(() => data?.items ?? [], [data?.items]);

  const counts: UserCounts = useMemo(() => ({
    all: items.length,
    pending: items.filter((u) => u.account_status === 'pending').length,
    approved: items.filter((u) => u.account_status === 'approved').length,
    suspended: items.filter((u) => u.account_status === 'suspended').length,
    rejected: items.filter((u) => u.account_status === 'rejected').length,
  }), [items]);

  const hasActiveFilters = Boolean(searchQuery.trim() || statusFilter !== 'all' || roleFilter !== 'all');

  const filteredUsers = useMemo(() => {
    let result = items;
    if (statusFilter !== 'all') result = result.filter((u) => u.account_status === statusFilter);
    if (roleFilter !== 'all') result = result.filter((u) => u.role === roleFilter);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));
    }
    return result;
  }, [items, statusFilter, roleFilter, searchQuery]);

  const toggleSelection = (userId: string) => {
    if (bulkDeactivationLock.current) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (bulkDeactivationLock.current) return;
    if (filteredUsers.length > 0 && filteredUsers.every((u) => selectedIds.has(u.user_id))) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredUsers.map((u) => u.user_id)));
    }
  };

  const isBulkDeactivating = isBulkDeactivationRunning || deactivateUser.isPending;

  const handleBulkDeactivate = () => {
    if (selectedIds.size === 0 || isBulkDeactivating) return;
    setBulkError(null);
    setIsBulkDeactivateOpen(true);
  };

  const confirmBulkDeactivate = async () => {
    if (bulkDeactivationLock.current || selectedIds.size === 0) return;
    bulkDeactivationLock.current = true;
    setIsBulkDeactivationRunning(true);
    setBulkError(null);
    const toDeactivate = Array.from(selectedIds);
    try {
      for (const userId of toDeactivate) {
        await deactivateUser.mutateAsync(userId);
        setSelectedIds((prev) => {
          const next = new Set(prev);
          next.delete(userId);
          return next;
        });
      }
      setIsBulkDeactivateOpen(false);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'detail' in err
        ? String(err.detail)
        : err instanceof Error
          ? err.message
          : 'Failed to deactivate users.';
      setBulkError(msg);
    } finally {
      bulkDeactivationLock.current = false;
      setIsBulkDeactivationRunning(false);
    }
  };

  const handleSuspend = (user: AdminUserResponse) => {
    setSuspendError(null);
    setUserToSuspend(user);
  };

  const confirmSuspend = async () => {
    if (!userToSuspend) return;
    setSuspendError(null);
    try {
      await setApproval.mutateAsync({ userId: userToSuspend.user_id, accountStatus: 'suspended' });
      setUserToSuspend(null);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'detail' in err
        ? String(err.detail)
        : err instanceof Error
          ? err.message
          : 'Failed to suspend user.';
      setSuspendError(msg);
    }
  };

  const handleDelete = (user: AdminUserResponse) => {
    setDeleteError(null);
    setUserToDelete(user);
  };

  const confirmDelete = async () => {
    if (!userToDelete) return;
    setDeleteError(null);
    try {
      await hardDeleteUser.mutateAsync(userToDelete.user_id);
      setUserToDelete(null);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'detail' in err
        ? String(err.detail)
        : err instanceof Error
          ? err.message
          : 'Failed to delete user.';
      setDeleteError(msg);
    }
  };

  return (
    <PageContainer as="section">
      <h1 className="sr-only">User Management</h1>

      {/* ── Search & Primary Action Row (matching DocumentDashboard) ── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-lg">
          <MagnifyingGlass
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search faculty by name or email…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-10 w-full rounded-sm border border-input bg-surface pl-9 pr-4 text-sm text-text placeholder:text-text-muted focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label="Search users"
          />
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {selectedIds.size > 0 ? (
            <button
              type="button"
              onClick={handleBulkDeactivate}
              disabled={isBulkDeactivating}
              className="inline-flex h-10 items-center gap-1.5 rounded-sm border border-destructive/30 bg-destructive-soft px-3.5 text-xs sm:text-sm font-semibold text-destructive hover:bg-destructive-soft/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive cursor-pointer disabled:opacity-50"
            >
              <UserMinus className="size-4" aria-hidden="true" />
              <span>Deactivate ({selectedIds.size})</span>
            </button>
          ) : null}

          <Button
            type="button"
            variant="primary"
            size="md"
            className="h-10 w-full shrink-0 gap-2 px-4 text-xs font-semibold sm:w-auto"
            onClick={() => setIsCreateModalOpen(true)}
          >
            <Plus className="size-4" aria-hidden="true" />
            <span>Create Faculty</span>
          </Button>
        </div>
      </div>

      {/* ── Filter & Sort Toolbar (matching StorageToolbar) ─────────── */}
      <div>
        <UserFiltersToolbar
          counts={counts}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          roleFilter={roleFilter}
          onRoleFilterChange={setRoleFilter}
          hasActiveFilters={hasActiveFilters}
          onResetFilters={() => {
            setStatusFilter('all');
            setRoleFilter('all');
            setSearchQuery('');
          }}
        />
      </div>

      {/* ── User Directory Ledger ──────────────────────────────────── */}
      <div
        className="flex flex-col overflow-hidden rounded-sm border border-border bg-surface shadow-none"
        role="region"
        aria-label="User Directory Ledger"
      >
        <UserTable
          users={filteredUsers}
          isLoading={isLoading}
          isError={isError}
          hasActiveFilters={hasActiveFilters}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelection}
          onToggleSelectAll={toggleSelectAll}
          onEdit={(user) => { setSelectedUser(user); setIsEditModalOpen(true); }}
          onApprove={(userId) => setApproval.mutate({ userId, accountStatus: 'approved' })}
          onReapprove={(userId) => setApproval.mutate({ userId, accountStatus: 'approved' })}
          onSuspend={handleSuspend}
          onReject={(userId) => setApproval.mutate({ userId, accountStatus: 'rejected' })}
          onDelete={handleDelete}
          isApprovalPending={setApproval.isPending}
          isDeletePending={hardDeleteUser.isPending}
        />
      </div>

      <CreateUserModal open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen} />
      <EditUserModal user={selectedUser} open={isEditModalOpen} onOpenChange={setIsEditModalOpen} />

      {/* Suspend Confirmation Modal */}
      <ConfirmationModal
        isOpen={Boolean(userToSuspend)}
        onClose={() => { setUserToSuspend(null); setSuspendError(null); }}
        onConfirm={confirmSuspend}
        title={`Suspend ${userToSuspend?.name || 'User'}?`}
        description={
          <div className="space-y-2">
            <p>
              Are you sure you want to suspend <strong className="text-text font-semibold">{userToSuspend?.name}</strong>?
            </p>
            <p className="text-xs text-text-muted">
              This will suspend the account, revoking their access to the system. You can reapprove it later.
            </p>
          </div>
        }
        confirmLabel="Suspend"
        cancelLabel="Cancel"
        variant="warning"
        isPending={setApproval.isPending}
        error={suspendError}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmationModal
        isOpen={Boolean(userToDelete)}
        onClose={() => { setUserToDelete(null); setDeleteError(null); }}
        onConfirm={confirmDelete}
        title={`Delete ${userToDelete?.name || 'User'}?`}
        description={
          <div className="space-y-2">
            <p>
              Are you sure you want to permanently delete <strong className="text-text font-semibold">{userToDelete?.name}</strong>?
            </p>
            <p className="text-xs text-destructive font-medium">
              This will permanently delete the account and cannot be undone.
            </p>
          </div>
        }
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="destructive"
        isPending={hardDeleteUser.isPending}
        error={deleteError}
      />

      {/* Bulk Deactivate Confirmation Modal */}
      <ConfirmationModal
        isOpen={isBulkDeactivateOpen}
        onClose={() => {
          if (bulkDeactivationLock.current) return;
          setIsBulkDeactivateOpen(false);
          setBulkError(null);
        }}
        onConfirm={confirmBulkDeactivate}
        title={`Deactivate ${selectedIds.size} user(s)?`}
        description={`Deactivate ${selectedIds.size} user(s)? This will deactivate their accounts. You can re-activate them later.`}
        confirmLabel={`Deactivate (${selectedIds.size})`}
        cancelLabel="Cancel"
        variant="destructive"
        isPending={isBulkDeactivating}
        error={bulkError}
      />
    </PageContainer>
  );
}
