import { useState, useMemo } from 'react';
import { Search, Plus, AlertTriangle } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { Skeleton } from '@/shared/components/ui/skeleton';
import { useAdminUsers } from '@/features/admin/hooks/useAdminUsers';
import { CreateUserModal } from './CreateUserModal';
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
        user.name.toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query)
    );
  }, [data, searchQuery]);

  return (
    <section className="grid gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Admin</p>
          <h1 className="mt-2 text-2xl font-semibold">User Management</h1>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="mr-2 size-4" />
          Create Faculty
        </Button>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="h-10 rounded-lg pl-9"
          placeholder="Search by name or email..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
        {isLoading ? (
          <div className="space-y-2 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center gap-2 py-12 text-destructive">
            <AlertTriangle className="size-5" />
            <span>Failed to load users.</span>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground">
            {searchQuery.trim() ? (
              <p>No users match your search.</p>
            ) : (
              <p>No users registered yet.</p>
            )}
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Registered</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredUsers.map((user: AdminUserResponse) => (
                <TableRow key={user.user_id}>
                  <TableCell className="font-medium">{user.name}</TableCell>
                  <TableCell className="text-muted-foreground">{user.email}</TableCell>
                  <TableCell>
                    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${
                      user.role === 'admin'
                        ? 'border-primary/50 text-primary bg-primary/10'
                        : 'border-muted-foreground/30 bg-muted/50'
                    }`}>
                      {user.role}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${
                      user.is_active
                        ? 'border-emerald-500/50 text-emerald-700 bg-emerald-50'
                        : 'border-muted-foreground/30 bg-muted/50'
                    }`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground text-sm">
                    {new Date(user.created_at).toLocaleDateString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <CreateUserModal open={isModalOpen} onOpenChange={setIsModalOpen} />
    </section>
  );
}
