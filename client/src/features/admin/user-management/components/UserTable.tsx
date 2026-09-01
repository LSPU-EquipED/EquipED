import { Warning } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES } from '@/shared/constants/theme';
import type { AdminUserResponse } from '../types';
import { UserTableRow } from './UserTableRow';

interface UserTableProps {
  users: AdminUserResponse[];
  isLoading: boolean;
  isError: boolean;
  hasActiveFilters: boolean;
  selectedIds: Set<string>;
  onToggleSelect: (userId: string) => void;
  onToggleSelectAll: () => void;
  onEdit: (user: AdminUserResponse) => void;
  onApprove: (userId: string) => void;
  onReapprove: (userId: string) => void;
  onSuspend: (user: AdminUserResponse) => void;
  onReject: (userId: string) => void;
  onDelete: (user: AdminUserResponse) => void;
  isApprovalPending?: boolean;
  isDeletePending?: boolean;
}

export function UserTable({
  users,
  isLoading,
  isError,
  hasActiveFilters,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  onEdit,
  onApprove,
  onReapprove,
  onSuspend,
  onReject,
  onDelete,
  isApprovalPending,
  isDeletePending,
}: UserTableProps) {
  const allSelected = users.length > 0 && users.every((user) => selectedIds.has(user.user_id));
  const someSelected = users.some((user) => selectedIds.has(user.user_id)) && !allSelected;

  if (isLoading) {
    return (
      <div className="space-y-2.5 p-6">
        <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
        <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
        <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-destructive font-semibold text-xs">
        <Warning className="size-4.5" aria-hidden="true" />
        <span>Failed to load users.</span>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="py-16 text-center text-text-muted font-medium text-xs space-y-1">
        <p className="font-semibold text-text">
          {hasActiveFilters ? 'No users match your filters' : 'No users registered yet'}
        </p>
        <p className="text-[11px] text-text-muted">
          {hasActiveFilters
            ? 'Try adjusting your search query or status filter.'
            : 'Create faculty accounts or review registration requests.'}
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className={TABLE_STYLES.table}>
        <thead className={TABLE_STYLES.thead}>
          <tr>
            <th scope="col" className="py-3 px-3 w-10 text-center">
              <input
                type="checkbox"
                checked={allSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someSelected;
                }}
                onChange={onToggleSelectAll}
                className="size-4 cursor-pointer accent-primary"
                aria-label="Select all users"
              />
            </th>
            <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[16rem]')}>
              User / Faculty
            </th>
            <th scope="col" className={TABLE_STYLES.th}>
              Role
            </th>
            <th scope="col" className={TABLE_STYLES.th}>
              Status
            </th>
            <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
              Registered
            </th>
            <th scope="col" className={cn(TABLE_STYLES.th, 'text-right min-w-[16rem] pr-6')}>
              Actions
            </th>
          </tr>
        </thead>
        <tbody className={TABLE_STYLES.tbody}>
          {users.map((user: AdminUserResponse) => (
            <UserTableRow
              key={user.user_id}
              user={user}
              isSelected={selectedIds.has(user.user_id)}
              onToggleSelect={onToggleSelect}
              onEdit={onEdit}
              onApprove={onApprove}
              onReapprove={onReapprove}
              onSuspend={onSuspend}
              onReject={onReject}
              onDelete={onDelete}
              isApprovalPending={isApprovalPending}
              isDeletePending={isDeletePending}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
