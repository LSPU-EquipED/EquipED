import { useState, useMemo } from 'react';
import { Search, Plus, AlertTriangle, Pencil, UserX, Trash2, UserCheck } from 'lucide-react';
import { useAdminUsers, useUpdateUser, useDeactivateUser, useHardDeleteUser } from '@/features/admin/hooks/useAdminUsers';
import { CreateUserModal } from '../components/CreateUserModal';
import { EditUserModal } from '../components/EditUserModal';
import type { AdminUserResponse } from '@/features/admin/types';

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

  const selectableUserIds = useMemo(
    () => new Set(filteredUsers.map((user) => user.user_id)),
    [filteredUsers],
  );

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
      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (const id of selectableUserIds) {
          next.delete(id);
        }
        return next;
      });
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (const id of selectableUserIds) {
          next.add(id);
        }
        return next;
      });
    }
  };

  const handleBulkDeactivate = () => {
    const count = selectedIds.size;
    if (
      count > 0 &&
      window.confirm(
        `Deactivate ${count} selected account${count === 1 ? '' : 's'}? You can re-activate them later.`,
      )
    ) {
      for (const userId of selectedIds) {
        deactivateUser.mutate(userId);
      }
      setSelectedIds(new Set());
    }
  };

  return (
    <section className="grid gap-6">
      <div className="flex items-center justify-end gap-3">
        {selectedIds.size > 0 ? (
          <button
            type="button"
            onClick={handleBulkDeactivate}
            disabled={deactivateUser.isPending}
            className="inline-flex h-10 items-center justify-center bg-[#b91c1c] hover:bg-[#b91c1c]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#b91c1c] focus:outline-none disabled:opacity-50"
          >
            <UserX className="mr-2 size-4" />
            Deactivate {selectedIds.size}
          </button>
        ) : null}
        <button
          type="button"
          className="inline-flex h-10 items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
          onClick={() => setIsCreateModalOpen(true)}
        >
          <Plus className="mr-2 size-4" />
          Create Faculty
        </button>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          className="w-full h-10 pl-9 pr-4 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-800"
          placeholder="Search by name or email..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        {isLoading ? (
          <div className="space-y-2.5 p-5">
            <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center gap-2 py-12 text-[#b91c1c] font-semibold">
            <AlertTriangle className="size-5" />
            <span>Failed to load users.</span>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-12 text-center text-slate-500 font-semibold text-sm">
            {searchQuery.trim() ? (
              <p>No users match your search.</p>
            ) : (
              <p>No users registered yet.</p>
            )}
          </div>
        ) : (
          <table className="w-full text-left border-collapse border-spacing-0">
            <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected;
                    }}
                    onChange={toggleSelectAll}
                    className="size-4 cursor-pointer accent-[#1b3b87]"
                    aria-label="Select all users"
                  />
                </th>
                <th className="py-3 px-4 font-semibold text-slate-500">Name</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Email</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Role</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Status</th>
                <th className="py-3 px-4 font-semibold text-slate-500 text-right">Registered</th>
                <th className="py-3 px-4 font-semibold text-slate-500 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {filteredUsers.map((user: AdminUserResponse) => (
                <tr key={user.user_id} className="hover:bg-slate-50/50">
                  <td className="py-3 px-4 text-center">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(user.user_id)}
                      onChange={() => toggleSelection(user.user_id)}
                      className="size-4 cursor-pointer accent-[#1b3b87]"
                      aria-label={`Select ${user.name}`}
                    />
                  </td>
                  <td className="py-3 px-4 text-sm font-semibold text-slate-900">{user.name}</td>
                  <td className="py-3 px-4 text-sm text-slate-600 font-medium">{user.email}</td>
                  <td className="py-3 px-4 text-sm">
                    <span
                      className={`inline-flex rounded-sm border px-2 py-0.5 text-xs font-semibold ${
                        user.role === 'admin'
                          ? 'border-slate-300 text-slate-800 bg-slate-100'
                          : 'border-slate-200 bg-slate-50 text-slate-600'
                      }`}
                    >
                      {user.role}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm">
                    <span
                      className={`inline-flex rounded-sm border px-2 py-0.5 text-xs font-semibold ${
                        user.is_active
                          ? 'border-[#3b963e]/30 text-[#3b963e] bg-[#3b963e]/10'
                          : 'border-slate-200 bg-slate-50 text-slate-600'
                      }`}
                    >
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-right text-slate-500 font-semibold">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedUser(user);
                          setIsEditModalOpen(true);
                        }}
                        className="inline-flex h-8 items-center justify-center gap-1.5 px-3 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
                        aria-label={`Edit ${user.name}`}
                      >
                        <Pencil className="size-3.5" />
                        Edit
                      </button>
                      {user.is_active ? (
                        <button
                          type="button"
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
                          className="inline-flex h-8 items-center justify-center gap-1.5 px-3 border border-[#b91c1c] text-[#b91c1c] hover:bg-[#b91c1c]/10 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#b91c1c] focus:outline-none disabled:opacity-50"
                          aria-label={`Deactivate ${user.name}`}
                        >
                          <UserX className="size-3.5" />
                          Deactivate
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            updateUser.mutate({ userId: user.user_id, body: { is_active: true } });
                          }}
                          disabled={updateUser.isPending}
                          className="inline-flex h-8 items-center justify-center gap-1.5 px-3 bg-[#3b963e] hover:bg-[#3b963e]/90 text-white rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#3b963e] focus:outline-none disabled:opacity-50"
                          aria-label={`Reactivate ${user.name}`}
                        >
                          <UserCheck className="size-3.5" />
                          Reactivate
                        </button>
                      )}
                      <button
                        type="button"
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
                        className="inline-flex h-8 items-center justify-center gap-1.5 px-3 bg-[#b91c1c] hover:bg-[#b91c1c]/90 text-white rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#b91c1c] focus:outline-none disabled:opacity-50"
                        aria-label={`Delete ${user.name}`}
                      >
                        <Trash2 className="size-3.5" />
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <CreateUserModal open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen} />
      <EditUserModal
        user={selectedUser}
        open={isEditModalOpen}
        onOpenChange={setIsEditModalOpen}
      />
    </section>
  );
}
