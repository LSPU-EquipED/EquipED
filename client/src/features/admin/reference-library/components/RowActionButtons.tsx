import { ExternalLink, Loader2, RefreshCw, Trash2 } from 'lucide-react';

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
    <div className="flex items-center justify-end gap-2">
      <button
        type="button"
        onClick={onPreview}
        disabled={isBusy}
        className="inline-flex h-8 items-center gap-1.5 border border-border bg-surface px-2.5 text-xs font-semibold uppercase tracking-wide text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm"
        title="Open PDF preview"
      >
        <ExternalLink className="size-3.5" />
        Preview
      </button>
      <button
        type="button"
        onClick={onRebuild}
        disabled={!canRebuild || isBusy}
        className="inline-flex h-8 items-center gap-1.5 border border-border bg-surface px-2.5 text-xs font-semibold uppercase tracking-wide text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm"
        title={rebuildTooltip}
      >
        {isRebuilding ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <RefreshCw className="size-3.5" />
        )}
        Rebuild
      </button>
      <button
        type="button"
        onClick={onDelete}
        disabled={isBusy}
        className="inline-flex h-8 items-center gap-1.5 border border-destructive/30 bg-destructive-soft px-2.5 text-xs font-semibold uppercase tracking-wide text-destructive transition-colors hover:bg-destructive-soft/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50 rounded-sm"
        title="Delete document and all associated data"
      >
        {isDeleting ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Trash2 className="size-3.5" />
        )}
        Delete
      </button>
    </div>
  );
}
