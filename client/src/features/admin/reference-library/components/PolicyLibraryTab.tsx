import { useMemo, useState } from 'react';
import { Link } from '@tanstack/react-router';
import { ArrowsClockwise, Scales, Spinner, UploadSimple } from '@phosphor-icons/react';
import {
  getReferenceFileUrl,
  getReferenceOperationError,
  useDeletePolicy,
  usePolicyLibrary,
  useRebuildPolicyEmbeddings,
} from '../hooks/useReferenceLibrary';
import { PolicyDeleteModal } from './DeleteModal';
import { PolicyRow } from './PolicyRow';

export function PolicyLibraryTab() {
  const { data, isLoading, isError, error, refetch } = usePolicyLibrary();
  const deletePolicy = useDeletePolicy();
  const rebuildPolicy = useRebuildPolicyEmbeddings();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const activeMutationId = deletePolicy.variables ?? rebuildPolicy.variables ?? null;
  const pendingDeleteId = deletePolicy.isPending ? deletePolicy.variables : null;
  const pendingRebuildId = rebuildPolicy.isPending ? rebuildPolicy.variables : null;

  const handlePreview = (documentId: string) => {
    window.open(getReferenceFileUrl(documentId), '_blank', 'noopener,noreferrer');
  };

  const handleRebuild = async (documentId: string) => {
    try {
      await rebuildPolicy.mutateAsync(documentId);
    } catch {
      // Error surfaced via mutation state
    }
  };

  const handleConfirmDelete = async () => {
    if (!confirmDeleteId) return;
    try {
      await deletePolicy.mutateAsync(confirmDeleteId);
      setConfirmDeleteId(null);
    } catch {
      // Error surfaced via mutation state
    }
  };

  const selectedItem = useMemo(
    () => items.find((item) => item.documentId === confirmDeleteId) ?? null,
    [items, confirmDeleteId],
  );

  const tableError =
    deletePolicy.isError || rebuildPolicy.isError
      ? deletePolicy.isError
        ? getReferenceOperationError(deletePolicy.error)
        : getReferenceOperationError(rebuildPolicy.error)
      : null;

  return (
    <>
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isLoading}
          className="inline-flex h-8 items-center gap-2 border border-border bg-surface px-3 text-xs font-semibold uppercase tracking-wide text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm"
          aria-label="Refresh policy list"
        >
          {isLoading ? (
            <Spinner className="size-4 animate-spin" />
          ) : (
            <ArrowsClockwise className="size-4" />
          )}
          Refresh
        </button>
      </div>

      {tableError ? (
        <div className="rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-sm font-semibold text-destructive">
          {tableError}
        </div>
      ) : null}

      <div className="border border-border bg-surface rounded-sm overflow-hidden">
        {isLoading ? (
          <div className="space-y-2.5 p-5">
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
          </div>
        ) : isError ? (
          <div className="py-12 text-center">
            <p className="text-sm font-semibold text-destructive">
              {getReferenceOperationError(error)}
            </p>
            <p className="mt-1 text-xs font-medium text-text-muted">
              Please try refreshing the page.
            </p>
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center">
            <Scales className="mx-auto size-8 text-text-muted" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-text">No policy documents found.</p>
            <p className="mt-1 text-xs font-medium text-text-muted">
              Upload a policy PDF with a recognized area to start the ITSO evidence library.
            </p>
            <Link
              to="/admin/ingest"
              className="mt-4 inline-flex h-10 items-center gap-2 bg-primary px-4 text-sm font-semibold uppercase tracking-wide text-primary-foreground transition-colors hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
            >
              <UploadSimple className="size-4" />
              Upload policy
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse border-spacing-0">
              <thead className="bg-surface-subtle text-text-muted uppercase text-[11px] tracking-wider font-semibold border-b border-border">
                <tr>
                  <th className="py-3 px-4 font-semibold text-text-muted">Title</th>
                  <th className="py-3 px-4 font-semibold text-text-muted">Policy area</th>
                  <th className="py-3 px-4 font-semibold text-text-muted">Status</th>
                  <th className="py-3 px-4 font-semibold text-text-muted">File</th>
                  <th className="py-3 px-4 font-semibold text-text-muted">Chunks</th>
                  <th className="py-3 px-4 font-semibold text-text-muted">Chroma</th>
                  <th className="py-3 px-4 font-semibold text-text-muted">Uploaded</th>
                  <th className="py-3 px-4 font-semibold text-text-muted text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => (
                  <PolicyRow
                    key={item.documentId}
                    item={item}
                    isBusy={activeMutationId === item.documentId}
                    isDeleting={pendingDeleteId === item.documentId}
                    isRebuilding={pendingRebuildId === item.documentId}
                    onPreview={() => handlePreview(item.documentId)}
                    onRebuild={() => handleRebuild(item.documentId)}
                    onDelete={() => setConfirmDeleteId(item.documentId)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {confirmDeleteId && selectedItem ? (
        <PolicyDeleteModal
          item={selectedItem}
          isDeleting={deletePolicy.isPending}
          onConfirm={handleConfirmDelete}
          onCancel={() => setConfirmDeleteId(null)}
        />
      ) : null}
    </>
  );
}
