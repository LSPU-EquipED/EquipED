import { useState, useMemo } from 'react';
import { Search, Plus, AlertTriangle } from 'lucide-react';
import { useAdminUsers } from '@/features/admin/hooks/useAdminUsers';
import { CreateUserModal } from '../components/CreateUserModal';
import type { AdminUserResponse } from '@/features/admin/types';

export function UserManagementPage() {
  const { data, isLoading, isError } = useAdminUsers();
  const [searchQuery, setSearchQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

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

  return (
    <section className="grid gap-6">
      <div className="flex items-center justify-end">
        <button
          type="button"
          className="inline-flex h-10 items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus className="mr-2 size-4" />
          Create Faculty
        </button>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          className="w-full h-10 pl-9 pr-4 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-400 font-semibold text-slate-800"
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
          <div className="flex items-center justify-center gap-2 py-12 text-red-700 font-semibold">
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
                <th className="py-3 px-4 font-semibold text-slate-500">Name</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Email</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Role</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Status</th>
                <th className="py-3 px-4 font-semibold text-slate-500 text-right">Registered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {filteredUsers.map((user: AdminUserResponse) => (
                <tr key={user.user_id} className="hover:bg-slate-50/50">
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
                          ? 'border-emerald-200 text-emerald-700 bg-emerald-50'
                          : 'border-slate-200 bg-slate-50 text-slate-600'
                      }`}
                    >
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-right text-slate-500 font-semibold">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <CreateUserModal open={isModalOpen} onOpenChange={setIsModalOpen} />
    </section>
  );
}
