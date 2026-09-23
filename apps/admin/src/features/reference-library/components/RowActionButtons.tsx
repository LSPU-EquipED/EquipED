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
    <div className="flex items-center justify-end gap-1">
      <button
        type="button"
        onClick={onPreview}
        disabled={isBusy}
        className="inline-flex size-8 items-center justify-center rounded-sm border border-border bg-surface text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 cursor-pointer"
        title="Open PDF preview"
        aria-label="Preview reference"
      >
        <ArrowSquareOut className="size-3.5" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={onRebuild}
        disabled={!canRebuild || isBusy}
        className="inline-flex size-8 items-center justify-center rounded-sm border border-border bg-surface text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 cursor-pointer"
        title={rebuildTooltip}
        aria-label="Rebuild reference index"
      >
        {isRebuilding ? (
          <Spinner className="size-3.5 motion-safe:animate-spin" aria-hidden="true" />
        ) : (
          <ArrowsClockwise className="size-3.5" aria-hidden="true" />
        )}
      </button>
      <button
        type="button"
        onClick={onDelete}
        disabled={isBusy}
        className="inline-flex size-8 items-center justify-center rounded-sm border border-destructive/30 bg-destructive-soft text-destructive transition-colors hover:bg-destructive-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50 cursor-pointer"
        title="Delete document and all associated data"
        aria-label="Delete reference"
      >
        {isDeleting ? (
          <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <Trash className="size-3.5" aria-hidden="true" />
        )}
      </button>
    </div>
  );
}
