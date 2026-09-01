import { useState, useMemo } from 'react';
import { TABLE_STYLES } from '@/shared/constants/theme';
import { CreateUserModal } from '../components/CreateUserModal';
import { EditUserModal } from '../components/EditUserModal';
import { UserFiltersToolbar, type RoleFilter, type StatusFilter } from '../components/UserFiltersToolbar';
import { UserMetricsBar, type UserCounts } from '../components/UserMetricsBar';
import { UserTable } from '../components/UserTable';
import {
  useAdminUsers,
  useDeactivateUser,
  useHardDeleteUser,
  useSetUserApproval,
} from '../hooks/useAdminUsers';
import type { AdminUserResponse } from '../types';

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

  const items = useMemo(() => data?.items ?? [], [data?.items]);

  const counts: UserCounts = useMemo(() => ({
    all: items.length,
    pending: items.filter((u) => u.account_status === 'pending').length,
    approved: items.filter((u) => u.account_status === 'approved').length,
    suspended: items.filter((u) => u.account_status === 'suspended').length,
    rejected: items.filter((u) => u.account_status === 'rejected').length,
  }), [items]);

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
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (filteredUsers.length > 0 && filteredUsers.every((u) => selectedIds.has(u.user_id))) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredUsers.map((u) => u.user_id)));
    }
  };

  const handleBulkDeactivate = () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`Deactivate ${selectedIds.size} user(s)? This will deactivate their accounts. You can re-activate them later.`)) return;
    for (const userId of selectedIds) deactivateUser.mutate(userId);
    setSelectedIds(new Set());
  };

  const handleSuspend = (user: AdminUserResponse) => {
    if (window.confirm(`Suspend ${user.name}? This will suspend the account. You can reapprove it later.`)) {
      setApproval.mutate({ userId: user.user_id, accountStatus: 'suspended' });
    }
  };

  const handleDelete = (user: AdminUserResponse) => {
    if (window.confirm(`Delete ${user.name}? This will permanently delete the account and cannot be undone. Are you sure?`)) {
      hardDeleteUser.mutate(user.user_id);
    }
  };

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-6">
      <UserMetricsBar counts={counts} />
      <div className={TABLE_STYLES.wrapper}>
        <UserFiltersToolbar
          counts={counts}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          roleFilter={roleFilter}
          onRoleFilterChange={setRoleFilter}
          searchQuery={searchQuery}
          onSearchQueryChange={setSearchQuery}
          selectedCount={selectedIds.size}
          onBulkDeactivate={handleBulkDeactivate}
          isDeactivating={deactivateUser.isPending}
          onCreateFaculty={() => setIsCreateModalOpen(true)}
        />
        <UserTable
          users={filteredUsers}
          isLoading={isLoading}
          isError={isError}
          hasActiveFilters={Boolean(searchQuery.trim() || statusFilter !== 'all' || roleFilter !== 'all')}
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
    </section>
  );
}
