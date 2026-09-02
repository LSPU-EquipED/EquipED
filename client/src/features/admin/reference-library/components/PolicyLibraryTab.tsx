import { useMemo, useState } from 'react';
import { Link } from '@tanstack/react-router';
import {
  ArrowsClockwise,
  MagnifyingGlass,
  Scales,
  Spinner,
  UploadSimple,
} from '@phosphor-icons/react';
import { BUTTON_STYLES, TABLE_STYLES } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';
import { TableSkeleton } from '@/shared/components/TableSkeleton';
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
  const [search, setSearch] = useState('');

  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const activeMutationId = deletePolicy.variables ?? rebuildPolicy.variables ?? null;
  const pendingDeleteId = deletePolicy.isPending ? deletePolicy.variables : null;
  const pendingRebuildId = rebuildPolicy.isPending ? rebuildPolicy.variables : null;

  const filteredItems = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        (item.policyArea && item.policyArea.toLowerCase().includes(q)),
    );
  }, [items, search]);

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
    <div className="space-y-4">
      {/* ── Table Toolbar ────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="relative min-w-[12rem] sm:min-w-[18rem]">
            <MagnifyingGlass
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Search policy manuals…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs font-medium text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Search policies"
            />
          </div>
          <span className="text-xs text-text-muted tabular-nums font-medium whitespace-nowrap">
            {items.length} polic{items.length === 1 ? 'y' : 'ies'} on record
          </span>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          disabled={isLoading}
          className="inline-flex h-8 items-center gap-1.5 border border-border bg-surface px-3 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm cursor-pointer shrink-0 self-end sm:self-auto"
          aria-label="Refresh policy list"
        >
          {isLoading ? (
            <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <ArrowsClockwise className="size-3.5" aria-hidden="true" />
          )}
          <span>Refresh</span>
        </button>
      </div>

      {/* ── Table Error Alert ────────────────────────────────────────── */}
      {tableError ? (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-xs font-semibold text-destructive"
        >
          {tableError}
        </div>
      ) : null}

      {/* ── Unified Ledger Table ─────────────────────────────────────── */}
      <div className={TABLE_STYLES.wrapper}>
        {isLoading ? (
          <TableSkeleton
            ariaLabel="Loading policy library"
            columns={[
              { label: 'Title', headerClassName: 'min-w-[16rem]', skeletonClassName: 'h-4 w-56' },
              { label: 'Policy area', skeletonClassName: 'h-4 w-28' },
              { label: 'Status', skeletonClassName: 'h-5 w-20' },
              { label: 'File', skeletonClassName: 'h-4 w-24' },
              { label: 'Chunks', skeletonClassName: 'h-4 w-12' },
              { label: 'Chroma', skeletonClassName: 'h-4 w-12' },
              { label: 'Uploaded', skeletonClassName: 'h-4 w-24' },
              { label: 'Actions', headerClassName: 'text-right', skeletonClassName: 'h-8 w-16 ml-auto' },
            ]}
          />
        ) : isError ? (
          <div className="py-16 text-center space-y-2">
            <p className="text-xs font-semibold text-destructive">
              {getReferenceOperationError(error)}
            </p>
            <p className="text-[11px] text-text-muted">
              Please try refreshing the page.
            </p>
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <Scales className="mx-auto size-8 text-text-muted/60" aria-hidden="true" />
            <div>
              <p className="text-xs font-bold text-text">No policy documents found</p>
              <p className="text-[11px] text-text-muted mt-0.5">
                Ingest official policy PDFs to support ITSO intellectual property evaluations.
              </p>
            </div>
            <Link
              to="/admin/ingest"
              className={cn(
                BUTTON_STYLES.base,
                BUTTON_STYLES.variants.primary,
                BUTTON_STYLES.sizes.sm,
                'text-xs h-8 px-3 inline-flex items-center gap-1.5',
              )}
            >
              <UploadSimple className="size-3.5" aria-hidden="true" />
              <span>Ingest policy</span>
            </Link>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <Scales className="mx-auto size-8 text-text-muted/60" aria-hidden="true" />
            <p className="text-xs font-bold text-text">No matching policies found</p>
            <p className="text-[11px] text-text-muted">
              Try adjusting your search query.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[16rem]')}>Title</th>
                  <th scope="col" className={TABLE_STYLES.th}>Policy area</th>
                  <th scope="col" className={TABLE_STYLES.th}>Status</th>
                  <th scope="col" className={TABLE_STYLES.th}>File</th>
                  <th scope="col" className={TABLE_STYLES.th}>Chunks</th>
                  <th scope="col" className={TABLE_STYLES.th}>Chroma</th>
                  <th scope="col" className={TABLE_STYLES.th}>Uploaded</th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>Actions</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {filteredItems.map((item) => (
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
    </div>
  );
}
