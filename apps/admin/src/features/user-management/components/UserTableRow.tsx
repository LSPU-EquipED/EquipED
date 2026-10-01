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
import { UserActionsMenu, type UserAction } from './UserActionsMenu';

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
  const approvalAction: UserAction =
    user.account_status === 'pending' || user.account_status === 'rejected'
      ? {
          label: 'Approve',
          icon: <UserCheck className="size-4" />,
          onSelect: () => onApprove(user.user_id),
          disabled: isApprovalPending,
        }
      : user.account_status === 'suspended' || !user.is_active
        ? {
            label: 'Reapprove',
            icon: <UserCheck className="size-4" />,
            onSelect: () => onReapprove(user.user_id),
            disabled: isApprovalPending,
          }
        : {
            label: 'Suspend',
            icon: <UserMinus className="size-4" />,
            onSelect: () => onSuspend(user),
            disabled: isApprovalPending,
          };
  const actions: UserAction[] = [
    {
      label: 'Edit',
      icon: <PencilSimple className="size-4" />,
      onSelect: () => onEdit(user),
    },
    approvalAction,
    ...(user.account_status === 'pending'
      ? [
          {
            label: 'Reject',
            icon: <X className="size-4" />,
            onSelect: () => onReject(user.user_id),
            disabled: isApprovalPending,
            destructive: true,
          },
        ]
      : []),
    {
      label: 'Delete',
      icon: <Trash className="size-4" />,
      onSelect: () => onDelete(user),
      disabled: isDeletePending,
      destructive: true,
    },
  ];

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
          <span className="font-semibold text-text line-clamp-1">
            {user.name}
          </span>
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
          {(user.evaluator_permissions || user.evaluatorPermissions || []).map(
            (perm) => (
              <span
                key={perm}
                className="inline-flex items-center rounded-xs bg-primary-soft/50 border border-primary/20 px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider text-primary"
              >
                {perm === 'coordinator' ? 'PC' : perm.toUpperCase()}
              </span>
            ),
          )}
        </div>
      </td>
      <td className={TABLE_STYLES.td}>
        <Badge variant={status.variant} withDot>
          {status.label}
        </Badge>
      </td>
      <td
        className={cn(
          TABLE_STYLES.tdData,
          'text-right text-xs text-text-muted tabular-nums font-medium',
        )}
      >
        {new Date(user.created_at).toLocaleDateString()}
      </td>
      <td className={cn(TABLE_STYLES.td, 'text-right w-20 min-w-[5rem] pr-6')}>
        <UserActionsMenu name={user.name} actions={actions} />
      </td>
    </tr>
  );
}
