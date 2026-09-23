import {
  PencilSimple,
  Trash,
  UserCheck,
  UserMinus,
  X,
} from '@phosphor-icons/react';
import { Badge } from '@equiped/ui';
import { cn } from '@equiped/ui';
import { TABLE_STYLES } from '@equiped/ui';
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
        <div className="flex flex-wrap items-center gap-1">
          <Badge variant={user.role === 'admin' ? 'accent' : 'neutral'}>
            {user.role}
          </Badge>
          {(user.evaluator_permissions || user.evaluatorPermissions || []).map((perm) => (
            <span
              key={perm}
              className="inline-flex items-center rounded-xs bg-primary-soft/50 border border-primary/20 px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider text-primary"
            >
              {perm === 'coordinator' ? 'PC' : perm.toUpperCase()}
            </span>
          ))}
        </div>
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
      <td className={cn(TABLE_STYLES.td, 'text-right w-32 min-w-[8rem] pr-6')}>
        <div className="flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={() => onEdit(user)}
            title={`Edit ${user.name}`}
            aria-label={`Edit ${user.name}`}
            className="cursor-pointer p-1 text-text-muted hover:text-text transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded-xs"
          >
            <PencilSimple className="size-4.5" aria-hidden="true" />
          </button>

          {user.account_status === 'pending' || user.account_status === 'rejected' ? (
            <button
              type="button"
              onClick={() => onApprove(user.user_id)}
              disabled={isApprovalPending}
              title={`Approve ${user.name}`}
              aria-label={`Approve ${user.name}`}
              className="cursor-pointer p-1 text-success hover:text-emerald-600 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-success rounded-xs disabled:opacity-40 disabled:pointer-events-none"
            >
              <UserCheck className="size-4.5" aria-hidden="true" />
            </button>
          ) : user.account_status === 'suspended' ? (
            <button
              type="button"
              onClick={() => onReapprove(user.user_id)}
              disabled={isApprovalPending}
              title={`Reapprove ${user.name}`}
              aria-label={`Reapprove ${user.name}`}
              className="cursor-pointer p-1 text-success hover:text-emerald-600 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-success rounded-xs disabled:opacity-40 disabled:pointer-events-none"
            >
              <UserCheck className="size-4.5" aria-hidden="true" />
            </button>
          ) : user.is_active ? (
            <button
              type="button"
              onClick={() => onSuspend(user)}
              disabled={isApprovalPending}
              title={`Suspend ${user.name}`}
              aria-label={`Suspend ${user.name}`}
              className="cursor-pointer p-1 text-warning hover:text-amber-600 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-warning rounded-xs disabled:opacity-40 disabled:pointer-events-none"
            >
              <UserMinus className="size-4.5" aria-hidden="true" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onReapprove(user.user_id)}
              disabled={isApprovalPending}
              title={`Reapprove ${user.name}`}
              aria-label={`Reapprove ${user.name}`}
              className="cursor-pointer p-1 text-success hover:text-emerald-600 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-success rounded-xs disabled:opacity-40 disabled:pointer-events-none"
            >
              <UserCheck className="size-4.5" aria-hidden="true" />
            </button>
          )}

          {user.account_status === 'pending' && (
            <button
              type="button"
              onClick={() => onReject(user.user_id)}
              disabled={isApprovalPending}
              title={`Reject ${user.name}`}
              aria-label={`Reject ${user.name}`}
              className="cursor-pointer p-1 text-destructive hover:text-red-700 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-destructive rounded-xs disabled:opacity-40 disabled:pointer-events-none"
            >
              <X className="size-4.5" aria-hidden="true" />
            </button>
          )}

          <button
            type="button"
            onClick={() => onDelete(user)}
            disabled={isDeletePending}
            title={`Delete ${user.name}`}
            aria-label={`Delete ${user.name}`}
            className="cursor-pointer p-1 text-destructive hover:text-red-700 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-destructive rounded-xs disabled:opacity-40 disabled:pointer-events-none"
          >
            <Trash className="size-4.5" aria-hidden="true" />
          </button>
        </div>
      </td>
    </tr>
  );
}
