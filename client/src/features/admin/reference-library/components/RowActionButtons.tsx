import { ArrowSquareOut, ArrowsClockwise, Spinner, Trash } from '@phosphor-icons/react';

interface RowActionButtonsProps {
  canRebuild: boolean;
  isBusy: boolean;
  isDeleting: boolean;
  isRebuilding: boolean;
  rebuildTooltip: string;
  onPreview: () => void;
  onRebuild: () => void;
  onDelete: () => void;
}

export function RowActionButtons({
  canRebuild,
  isBusy,
  isDeleting,
  isRebuilding,
  rebuildTooltip,
  onPreview,
  onRebuild,
  onDelete,
}: RowActionButtonsProps) {
  return (
    <div className="flex items-center justify-end gap-1.5">
      <button
        type="button"
        onClick={onPreview}
        disabled={isBusy}
        className="inline-flex h-7.5 items-center gap-1.5 border border-border bg-surface px-2.5 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm cursor-pointer"
        title="Open PDF preview"
      >
        <ArrowSquareOut className="size-3.5" aria-hidden="true" />
        <span>Preview</span>
      </button>
      <button
        type="button"
        onClick={onRebuild}
        disabled={!canRebuild || isBusy}
        className="inline-flex h-7.5 items-center gap-1.5 border border-border bg-surface px-2.5 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm cursor-pointer"
        title={rebuildTooltip}
      >
        {isRebuilding ? (
          <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <ArrowsClockwise className="size-3.5" aria-hidden="true" />
        )}
        <span>Rebuild</span>
      </button>
      <button
        type="button"
        onClick={onDelete}
        disabled={isBusy}
        className="inline-flex h-7.5 items-center gap-1.5 border border-destructive/30 bg-destructive-soft px-2.5 text-xs font-semibold text-destructive transition-colors hover:bg-destructive-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50 rounded-sm cursor-pointer"
        title="Delete document and all associated data"
      >
        {isDeleting ? (
          <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <Trash className="size-3.5" aria-hidden="true" />
        )}
        <span>Delete</span>
      </button>
    </div>
  );
}
