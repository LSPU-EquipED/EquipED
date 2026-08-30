import { useMemo, useState } from 'react';
import { Link } from '@tanstack/react-router';
import { BookOpen, Loader2, RefreshCw, Upload } from 'lucide-react';
import { cn } from '@/shared/components/utils';
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
    if (filterType === 'all') return items;
    return items.filter((item) => item.sourceType === filterType);
  }, [items, filterType]);

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
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setFilterType('all')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              filterType === 'all'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            All
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
                filterType === 'all' ? 'bg-primary-foreground/20 text-primary-foreground' : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.all}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setFilterType('syllabus')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              filterType === 'syllabus'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            Syllabus
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
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
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              filterType === 'curriculum'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            Curriculum
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
                filterType === 'curriculum'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.curriculum}
            </span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isLoading}
            className="inline-flex h-8 items-center gap-2 border border-border bg-surface px-3 text-xs font-semibold uppercase tracking-wide text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm"
            aria-label="Refresh reference list"
          >
            {isLoading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="size-3.5" />
            )}
            Refresh
          </button>
        </div>
      </div>

      {tableError ? (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-sm font-semibold text-destructive"
        >
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
            <BookOpen className="mx-auto size-8 text-text-muted" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-text">No references found.</p>
            <p className="mt-1 text-xs font-medium text-text-muted">
              Upload a syllabus or curriculum to get started.
            </p>
            <Link
              to="/admin/ingest"
              className="mt-4 inline-flex h-10 items-center gap-2 bg-primary px-4 text-sm font-semibold uppercase tracking-wide text-primary-foreground transition-colors hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
            >
              <Upload className="size-4" />
              Upload reference
            </Link>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="py-12 text-center">
            <BookOpen className="mx-auto size-8 text-text-muted" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-text">
              No {filterType} references found.
            </p>
            <p className="mt-1 text-xs font-medium text-text-muted">
              Select another filter or upload a new {filterType} reference.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse border-spacing-0">
              <thead className="bg-surface-subtle text-text-muted uppercase text-[11px] tracking-wider font-semibold border-b border-border">
                <tr>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Title</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Type</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Program</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Course code</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Sem / AY</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Lesson</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Status</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">File</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Chunks</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Chroma</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted">Uploaded</th>
                  <th scope="col" className="py-3 px-4 font-semibold text-text-muted text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
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
    </>
  );
}
