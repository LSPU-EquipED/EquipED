import { UserMinus, X } from '@phosphor-icons/react';

interface UserBatchActionsBarProps {
  selectedCount: number;
  onBulkDeactivate: () => void;
  onClearSelection: () => void;
  isPending?: boolean;
}

export function UserBatchActionsBar({
  selectedCount,
  onBulkDeactivate,
  onClearSelection,
  isPending,
}: UserBatchActionsBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onBulkDeactivate}
        disabled={isPending}
        className="inline-flex h-10 items-center gap-1.5 rounded-sm border border-destructive/30 bg-destructive-soft px-3.5 text-xs sm:text-sm font-semibold text-destructive hover:bg-destructive-soft/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive cursor-pointer disabled:opacity-50"
      >
        <UserMinus className="size-4" aria-hidden="true" />
        <span>Deactivate ({selectedCount})</span>
      </button>

      <button
        type="button"
        onClick={onClearSelection}
        className="inline-flex h-10 items-center gap-1 rounded-sm border border-border bg-surface px-2.5 text-xs font-semibold text-text-muted hover:text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
        aria-label="Clear selection"
      >
        <X className="size-3.5" aria-hidden="true" />
        <span>Clear</span>
      </button>
    </div>
  );
}
