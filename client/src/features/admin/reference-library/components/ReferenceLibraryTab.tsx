import { useMemo, useState } from 'react';
import { Link } from '@tanstack/react-router';
import {
  ArrowsClockwise,
  Books,
  MagnifyingGlass,
  Spinner,
  UploadSimple,
} from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES, TABLE_STYLES } from '@/shared/constants/theme';
import {
  getReferenceFileUrl,
  getReferenceOperationError,
  useDeleteReference,
  useRebuildReferenceEmbeddings,
  useReferenceLibrary,
} from '../hooks/useReferenceLibrary';
import { ReferenceDeleteModal } from './DeleteModal';
import { ReferenceRow } from './ReferenceRow';

type ReferenceFilterType = 'all' | 'syllabus' | 'curriculum';

export function ReferenceLibraryTab() {
  const { data, isLoading, isError, error, refetch } = useReferenceLibrary();
  const deleteReference = useDeleteReference();
  const rebuildReference = useRebuildReferenceEmbeddings();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<ReferenceFilterType>('all');
  const [search, setSearch] = useState('');

  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const pendingDeleteId = deleteReference.isPending ? deleteReference.variables : null;
  const pendingRebuildId = rebuildReference.isPending ? rebuildReference.variables : null;
  const busyDocumentId = pendingDeleteId ?? pendingRebuildId ?? null;

  const counts = useMemo(() => {
    return {
      all: items.length,
      syllabus: items.filter((i) => i.sourceType === 'syllabus').length,
      curriculum: items.filter((i) => i.sourceType === 'curriculum').length,
    };
  }, [items]);

  const filteredItems = useMemo(() => {
    let result = items;
    if (filterType !== 'all') {
      result = result.filter((item) => item.sourceType === filterType);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (item) =>
          item.title.toLowerCase().includes(q) ||
          (item.courseCode && item.courseCode.toLowerCase().includes(q)) ||
          (item.program && item.program.toLowerCase().includes(q)) ||
          (item.academicYear && item.academicYear.toLowerCase().includes(q)),
      );
    }
    return result;
  }, [items, filterType, search]);

  const handlePreview = (documentId: string) => {
    window.open(getReferenceFileUrl(documentId), '_blank', 'noopener,noreferrer');
  };

  const handleRebuild = async (documentId: string) => {
    try {
      await rebuildReference.mutateAsync(documentId);
    } catch {
      // Error surfaced via mutation state
    }
  };

  const handleConfirmDelete = async () => {
    if (!confirmDeleteId) return;
    try {
      await deleteReference.mutateAsync(confirmDeleteId);
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
    deleteReference.isError || rebuildReference.isError
      ? deleteReference.isError
        ? getReferenceOperationError(deleteReference.error)
        : getReferenceOperationError(rebuildReference.error)
      : null;

  return (
    <div className="space-y-4">
      {/* ── Table Toolbar ────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            type="button"
            onClick={() => setFilterType('all')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              filterType === 'all'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            <span>All</span>
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
                filterType === 'all'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.all}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setFilterType('syllabus')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              filterType === 'syllabus'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            <span>Syllabus</span>
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
                filterType === 'syllabus'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.syllabus}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setFilterType('curriculum')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              filterType === 'curriculum'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            <span>Curriculum</span>
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
                filterType === 'curriculum'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.curriculum}
            </span>
          </button>
        </div>

        {/* Right Search & Refresh Controls */}
        <div className="flex items-center gap-2">
          <div className="relative min-w-[12rem] sm:min-w-[16rem]">
            <MagnifyingGlass
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Search references…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs font-medium text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Search references"
            />
          </div>

          <button
            type="button"
            onClick={() => refetch()}
            disabled={isLoading}
            className="inline-flex h-8 items-center gap-1.5 border border-border bg-surface px-3 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm cursor-pointer shrink-0"
            aria-label="Refresh reference list"
          >
            {isLoading ? (
              <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <ArrowsClockwise className="size-3.5" aria-hidden="true" />
            )}
            <span>Refresh</span>
          </button>
        </div>
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
          <div className="space-y-2.5 p-6">
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-8 w-full rounded-sm" />
          </div>
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
            <Books className="mx-auto size-8 text-text-muted/60" aria-hidden="true" />
            <div>
              <p className="text-xs font-bold text-text">No references found</p>
              <p className="text-[11px] text-text-muted mt-0.5">
                Ingest official syllabi or curricula to make them available for evaluation alignment.
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
              <span>Ingest reference</span>
            </Link>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <Books className="mx-auto size-8 text-text-muted/60" aria-hidden="true" />
            <p className="text-xs font-bold text-text">
              No matching {filterType !== 'all' ? filterType : ''} references
            </p>
            <p className="text-[11px] text-text-muted">
              Adjust your search query or switch filters to view other references.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[16rem]')}>Title</th>
                  <th scope="col" className={TABLE_STYLES.th}>Type</th>
                  <th scope="col" className={TABLE_STYLES.th}>Program</th>
                  <th scope="col" className={TABLE_STYLES.th}>Course code</th>
                  <th scope="col" className={TABLE_STYLES.th}>Sem / AY</th>
                  <th scope="col" className={TABLE_STYLES.th}>Lesson</th>
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
                  <ReferenceRow
                    key={item.documentId}
                    item={item}
                    isBusy={busyDocumentId === item.documentId}
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
        <ReferenceDeleteModal
          item={selectedItem}
          isDeleting={deleteReference.isPending}
          onConfirm={handleConfirmDelete}
          onCancel={() => setConfirmDeleteId(null)}
        />
      ) : null}
    </div>
  );
}
