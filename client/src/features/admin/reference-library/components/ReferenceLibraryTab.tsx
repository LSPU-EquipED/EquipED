import { useMemo, useState } from 'react';
import { Link } from '@tanstack/react-router';
import { BookOpen, Loader2, RefreshCw, Upload } from 'lucide-react';
import {
  getReferenceFileUrl,
  getReferenceOperationError,
  useDeleteReference,
  useRebuildReferenceEmbeddings,
  useReferenceLibrary,
} from '../hooks/useReferenceLibrary';
import { ReferenceDeleteModal } from './DeleteModal';
import { ReferenceRow } from './ReferenceRow';

export function ReferenceLibraryTab() {
  const { data, isLoading, isError, error, refetch } = useReferenceLibrary();
  const deleteReference = useDeleteReference();
  const rebuildReference = useRebuildReferenceEmbeddings();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const activeMutationId = deleteReference.variables ?? rebuildReference.variables ?? null;
  const pendingDeleteId = deleteReference.isPending ? deleteReference.variables : null;
  const pendingRebuildId = rebuildReference.isPending ? rebuildReference.variables : null;

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
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isLoading}
          className="inline-flex h-10 items-center gap-2 border border-slate-200 bg-white px-3 text-sm font-semibold uppercase tracking-wide text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 rounded-sm"
          aria-label="Refresh reference list"
        >
          {isLoading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <RefreshCw className="size-4" />
          )}
          Refresh
        </button>
      </div>

      {tableError ? (
        <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm font-semibold text-[#b91c1c]">
          {tableError}
        </div>
      ) : null}

      <div className="border border-slate-200 bg-white rounded-sm overflow-hidden">
        {isLoading ? (
          <div className="space-y-2.5 p-5">
            <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
            <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
          </div>
        ) : isError ? (
          <div className="py-12 text-center">
            <p className="text-sm font-semibold text-[#b91c1c]">
              {getReferenceOperationError(error)}
            </p>
            <p className="mt-1 text-xs font-medium text-slate-400">
              Please try refreshing the page.
            </p>
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center">
            <BookOpen className="mx-auto size-8 text-slate-300" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-slate-600">No references found.</p>
            <p className="mt-1 text-xs font-medium text-slate-500">
              Upload a syllabus or curriculum to get started.
            </p>
            <Link
              to="/admin/ingest"
              className="mt-4 inline-flex h-10 items-center gap-2 bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm"
            >
              <Upload className="size-4" />
              Upload reference
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse border-spacing-0">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4 font-semibold text-slate-500">Title</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Type</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Course code</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Sem / AY</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Lesson</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Status</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">File</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Chunks</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Chroma</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Uploaded</th>
                  <th className="py-3 px-4 font-semibold text-slate-500 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {items.map((item) => (
                  <ReferenceRow
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
