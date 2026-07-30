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
        className="inline-flex h-8 items-center gap-1.5 border border-slate-200 bg-white px-2.5 text-xs font-semibold uppercase tracking-wide text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 rounded-sm"
        title="Open PDF preview"
      >
        <ExternalLink className="size-3.5" />
        Preview
      </button>
      <button
        type="button"
        onClick={onRebuild}
        disabled={!canRebuild || isBusy}
        className="inline-flex h-8 items-center gap-1.5 border border-slate-200 bg-white px-2.5 text-xs font-semibold uppercase tracking-wide text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 rounded-sm"
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
        className="inline-flex h-8 items-center gap-1.5 border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-2.5 text-xs font-semibold uppercase tracking-wide text-[#b91c1c] transition-colors hover:bg-[#b91c1c]/20 focus:outline-none focus:ring-2 focus:ring-[#b91c1c] disabled:opacity-50 rounded-sm"
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
