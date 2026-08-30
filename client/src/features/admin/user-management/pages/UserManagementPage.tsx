import { useState, useMemo } from 'react';
import {
  MagnifyingGlass,
  PencilSimple,
  Plus,
  Trash,
  UserCheck,
  UserMinus,
  Warning,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { INPUT_STYLES, TABLE_STYLES } from '@/shared/constants/theme';
import { CreateUserModal } from '../components/CreateUserModal';
import { EditUserModal } from '../components/EditUserModal';
import {
  useAdminUsers,
  useUpdateUser,
  useDeactivateUser,
  useHardDeleteUser,
} from '../hooks/useAdminUsers';
import type { AdminUserResponse } from '../types';

export function UserManagementPage() {
  const { data, isLoading, isError } = useAdminUsers();
  const updateUser = useUpdateUser();
  const deactivateUser = useDeactivateUser();
  const hardDeleteUser = useHardDeleteUser();
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<AdminUserResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const filteredUsers = useMemo(() => {
    const items = data?.items;
    if (!items) return [];
    if (!searchQuery.trim()) return items;
    const query = searchQuery.toLowerCase();
    return items.filter(
      (user: AdminUserResponse) =>
        user.name.toLowerCase().includes(query) || user.email.toLowerCase().includes(query),
    );
  }, [data, searchQuery]);

  const allSelected =
    filteredUsers.length > 0 && filteredUsers.every((user) => selectedIds.has(user.user_id));
  const someSelected = filteredUsers.some((user) => selectedIds.has(user.user_id)) && !allSelected;

  const toggleSelection = (userId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredUsers.map((user) => user.user_id)));
    }
  };

  const handleBulkDeactivate = () => {
    if (selectedIds.size === 0) return;
    if (
      !window.confirm(
        `Deactivate ${selectedIds.size} user(s)? This will deactivate their accounts. You can re-activate them later.`,
      )
    ) {
      return;
    }

    for (const userId of selectedIds) {
      deactivateUser.mutate(userId);
    }
    setSelectedIds(new Set());
  };

  return (
    <section className="grid gap-6">
      <div className="flex items-center justify-end gap-3">
        {selectedIds.size > 0 ? (
          <Button
            type="button"
            variant="destructive"
            onClick={handleBulkDeactivate}
            disabled={deactivateUser.isPending}
            className="text-xs font-semibold uppercase tracking-wider"
          >
            <UserMinus className="size-4" />
            Deactivate {selectedIds.size}
          </Button>
        ) : null}
        <Button
          type="button"
          variant="primary"
          className="text-xs font-semibold uppercase tracking-wider"
          onClick={() => setIsCreateModalOpen(true)}
        >
          <Plus className="size-4" />
          Create Faculty
        </Button>
      </div>

      <div className="relative">
        <MagnifyingGlass className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          className={cn(
            INPUT_STYLES.base,
            'pl-9 pr-4 font-medium text-text placeholder:text-text-muted',
          )}
          placeholder="Search by name or email..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div className={TABLE_STYLES.wrapper}>
        {isLoading ? (
          <div className="space-y-2.5 p-5">
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center gap-2 py-12 text-destructive font-semibold">
            <Warning className="size-5" />
            <span>Failed to load users.</span>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-12 text-center text-text-muted font-medium text-sm">
            {searchQuery.trim() ? (
              <p>No users match your search.</p>
            ) : (
              <p>No users registered yet.</p>
            )}
          </div>
        ) : (
          <table className={TABLE_STYLES.table}>
            <thead className={TABLE_STYLES.thead}>
              <tr>
                <th className="py-3 px-4 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected;
                    }}
                    onChange={toggleSelectAll}
                    className="size-4 cursor-pointer accent-primary"
                    aria-label="Select all users"
                  />
                </th>
                <th className={TABLE_STYLES.th}>Name</th>
                <th className={TABLE_STYLES.th}>Email</th>
                <th className={TABLE_STYLES.th}>Role</th>
                <th className={TABLE_STYLES.th}>Status</th>
                <th className={cn(TABLE_STYLES.th, 'text-right')}>Registered</th>
                <th className={cn(TABLE_STYLES.th, 'text-center')}>Actions</th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {filteredUsers.map((user: AdminUserResponse) => (
                <tr key={user.user_id} className={TABLE_STYLES.tr}>
                  <td className="py-3 px-4 text-center">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(user.user_id)}
                      onChange={() => toggleSelection(user.user_id)}
                      className="size-4 cursor-pointer accent-primary"
                      aria-label={`Select ${user.name}`}
                    />
                  </td>
                  <td className={cn(TABLE_STYLES.td, 'font-semibold text-text')}>{user.name}</td>
                  <td className={cn(TABLE_STYLES.td, 'text-text-muted font-medium')}>{user.email}</td>
                  <td className={TABLE_STYLES.td}>
                    <Badge variant={user.role === 'admin' ? 'accent' : 'neutral'}>
                      {user.role}
                    </Badge>
                  </td>
                  <td className={TABLE_STYLES.td}>
                    <Badge variant={user.is_active ? 'success' : 'neutral'} withDot>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  <td className={cn(TABLE_STYLES.tdData, 'text-right text-text-muted font-medium')}>
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className={TABLE_STYLES.td}>
                    <div className="flex items-center justify-center gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setSelectedUser(user);
                          setIsEditModalOpen(true);
                        }}
                        className="text-xs uppercase tracking-wider font-semibold"
                        aria-label={`Edit ${user.name}`}
                      >
                        <PencilSimple className="size-3.5" />
                        Edit
                      </Button>
                      {user.is_active ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (
                              window.confirm(
                                `Deactivate ${user.name}? This will deactivate the account. You can re-activate it later.`,
                              )
                            ) {
                              deactivateUser.mutate(user.user_id);
                            }
                          }}
                          disabled={deactivateUser.isPending}
                          className="border-destructive/30 text-destructive hover:bg-destructive-soft hover:text-destructive text-xs uppercase tracking-wider font-semibold"
                          aria-label={`Deactivate ${user.name}`}
                        >
                          <UserMinus className="size-3.5" />
                          Deactivate
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            updateUser.mutate({ userId: user.user_id, body: { is_active: true } });
                          }}
                          disabled={updateUser.isPending}
                          className="bg-success hover:bg-success/90 text-success-foreground text-xs uppercase tracking-wider font-semibold"
                          aria-label={`Reactivate ${user.name}`}
                        >
                          <UserCheck className="size-3.5" />
                          Reactivate
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        onClick={() => {
                          if (
                            window.confirm(
                              `Delete ${user.name}? This will permanently delete the account and cannot be undone. Are you sure?`,
                            )
                          ) {
                            hardDeleteUser.mutate(user.user_id);
                          }
                        }}
                        disabled={hardDeleteUser.isPending}
                        className="text-xs uppercase tracking-wider font-semibold"
                        aria-label={`Delete ${user.name}`}
                      >
                        <Trash className="size-3.5" />
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <CreateUserModal open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen} />
      <EditUserModal user={selectedUser} open={isEditModalOpen} onOpenChange={setIsEditModalOpen} />
    </section>
  );
}
