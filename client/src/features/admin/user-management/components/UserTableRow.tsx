import {
  PencilSimple,
  Trash,
  UserCheck,
  UserMinus,
  X,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES } from '@/shared/constants/theme';
import type { AdminUserResponse } from '../types';
import { getUserStatusBadge } from '../utils/userStatus';

interface UserTableRowProps {
  user: AdminUserResponse;
  isSelected: boolean;
  onToggleSelect: (userId: string) => void;
  onEdit: (user: AdminUserResponse) => void;
  onApprove: (userId: string) => void;
  onReapprove: (userId: string) => void;
  onSuspend: (user: AdminUserResponse) => void;
  onReject: (userId: string) => void;
  onDelete: (user: AdminUserResponse) => void;
  isApprovalPending?: boolean;
  isDeletePending?: boolean;
}

export function UserTableRow({
  user,
  isSelected,
  onToggleSelect,
  onEdit,
  onApprove,
  onReapprove,
  onSuspend,
  onReject,
  onDelete,
  isApprovalPending,
  isDeletePending,
}: UserTableRowProps) {
  const status = getUserStatusBadge(user);

  return (
    <tr className={TABLE_STYLES.tr}>
      <td className="py-3 px-3 text-center">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggleSelect(user.user_id)}
          className="size-4 cursor-pointer accent-primary"
          aria-label={`Select ${user.name}`}
        />
      </td>
      <td className={TABLE_STYLES.td}>
        <div className="flex flex-col">
          <span className="font-semibold text-text line-clamp-1">{user.name}</span>
          <span className="text-xs text-text-muted font-medium mt-0.5">
            {user.email}
          </span>
        </div>
      </td>
      <td className={TABLE_STYLES.td}>
        <Badge variant={user.role === 'admin' ? 'accent' : 'neutral'}>
          {user.role}
        </Badge>
      </td>
      <td className={TABLE_STYLES.td}>
        <Badge variant={status.variant} withDot>
          {status.label}
        </Badge>
      </td>
      <td
        className={cn(TABLE_STYLES.tdData, 'text-right text-xs text-text-muted tabular-nums font-medium')}
      >
        {new Date(user.created_at).toLocaleDateString()}
      </td>
      <td className={cn(TABLE_STYLES.td, 'text-right pr-6')}>
        <div className="flex items-center justify-end gap-1.5">
          <button
            type="button"
            onClick={() => onEdit(user)}
            className="inline-flex h-8 items-center gap-1.5 border border-border bg-surface px-3 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm cursor-pointer"
            aria-label={`Edit ${user.name}`}
          >
            <PencilSimple className="size-3.5" aria-hidden="true" />
            <span>Edit</span>
          </button>

          {user.account_status === 'pending' || user.account_status === 'rejected' ? (
            <button
              type="button"
              onClick={() => onApprove(user.user_id)}
              disabled={isApprovalPending}
              className="inline-flex h-7.5 items-center gap-1.5 border border-success/30 bg-success-soft px-2.5 text-xs font-semibold text-success transition-colors hover:bg-success-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success rounded-sm cursor-pointer disabled:opacity-50"
              aria-label={`Approve ${user.name}`}
            >
              <UserCheck className="size-3.5" aria-hidden="true" />
              <span>Approve</span>
            </button>
          ) : user.account_status === 'suspended' ? (
            <button
              type="button"
              onClick={() => onReapprove(user.user_id)}
              disabled={isApprovalPending}
              className="inline-flex h-7.5 items-center gap-1.5 border border-success/30 bg-success-soft px-2.5 text-xs font-semibold text-success transition-colors hover:bg-success-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success rounded-sm cursor-pointer disabled:opacity-50"
              aria-label={`Reapprove ${user.name}`}
            >
              <UserCheck className="size-3.5" aria-hidden="true" />
              <span>Reapprove</span>
            </button>
          ) : user.is_active ? (
            <button
              type="button"
              onClick={() => onSuspend(user)}
              disabled={isApprovalPending}
              className="inline-flex h-7.5 items-center gap-1.5 border border-warning/30 bg-warning-soft px-2.5 text-xs font-semibold text-warning transition-colors hover:bg-warning-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning rounded-sm cursor-pointer disabled:opacity-50"
              aria-label={`Suspend ${user.name}`}
            >
              <UserMinus className="size-3.5" aria-hidden="true" />
              <span>Suspend</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onReapprove(user.user_id)}
              disabled={isApprovalPending}
              className="inline-flex h-7.5 items-center gap-1.5 border border-success/30 bg-success-soft px-2.5 text-xs font-semibold text-success transition-colors hover:bg-success-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success rounded-sm cursor-pointer disabled:opacity-50"
              aria-label={`Reapprove ${user.name}`}
            >
              <UserCheck className="size-3.5" aria-hidden="true" />
              <span>Reapprove</span>
            </button>
          )}

          {user.account_status === 'pending' && (
            <button
              type="button"
              onClick={() => onReject(user.user_id)}
              disabled={isApprovalPending}
              className="inline-flex h-7.5 items-center gap-1.5 border border-destructive/30 bg-destructive-soft px-2.5 text-xs font-semibold text-destructive transition-colors hover:bg-destructive-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive rounded-sm cursor-pointer disabled:opacity-50"
              aria-label={`Reject ${user.name}`}
            >
              <X className="size-3.5" aria-hidden="true" />
              <span>Reject</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => onDelete(user)}
            disabled={isDeletePending}
            className="inline-flex h-7.5 items-center gap-1.5 border border-destructive/30 bg-destructive-soft px-2.5 text-xs font-semibold text-destructive transition-colors hover:bg-destructive-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive rounded-sm cursor-pointer disabled:opacity-50"
            aria-label={`Delete ${user.name}`}
          >
            <Trash className="size-3.5" aria-hidden="true" />
            <span>Delete</span>
          </button>
        </div>
      </td>
    </tr>
  );
}
