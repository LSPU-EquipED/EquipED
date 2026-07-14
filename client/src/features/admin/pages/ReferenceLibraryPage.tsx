import { useMemo, useState } from 'react';
import { Link } from '@tanstack/react-router';
import {
  AlertTriangle,
  BookOpen,
  ExternalLink,
  Loader2,
  RefreshCw,
  Scale,
  Trash2,
  Upload,
} from 'lucide-react';
import { cn } from '@/shared/components/utils';
import {
  POLICY_AREA_LABELS,
  type PolicyArea,
  type PolicyLibraryItem,
  type ReferenceLibraryItem,
} from '@/shared/types/documents';
import {
  useDeletePolicy,
  useDeleteReference,
  usePolicyLibrary,
  useRebuildPolicyEmbeddings,
  useRebuildReferenceEmbeddings,
  useReferenceLibrary,
  getReferenceFileUrl,
  getReferenceOperationError,
} from '@/features/admin/hooks/useReferenceLibrary';

type LibraryTab = 'references' | 'policies';

const referenceTypeLabels: Record<string, string> = {
  syllabus: 'Syllabus',
  curriculum: 'Curriculum',
};

const policyAreaLabelMap = POLICY_AREA_LABELS as Record<PolicyArea, string>;

function isPolicyArea(value: string | null | undefined): value is PolicyArea {
  return value !== null && value !== undefined && value in policyAreaLabelMap;
}

function processingStatusClass(status: string): string {
  if (status === 'PROCESSED') return 'bg-[#3b963e] text-white';
  if (status === 'FAILED') return 'bg-[#b91c1c] text-white';
  return 'bg-[#f2c811] text-[#1e293b]';
}

function healthBadgeClass(healthy: boolean): string {
  return healthy
    ? 'bg-[#3b963e]/10 text-[#3b963e] border-[#3b963e]/20'
    : 'bg-[#b91c1c]/10 text-[#b91c1c] border-[#b91c1c]/20';
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function ReferenceLibraryPage() {
  const [activeTab, setActiveTab] = useState<LibraryTab>('references');

  return (
    <section className="grid gap-5">
      <PageHeader />
      <div
        role="tablist"
        aria-label="Reference library sections"
        className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-1"
      >
        <LibraryTabButton
          id="library-tab-references"
          isActive={activeTab === 'references'}
          onSelect={() => setActiveTab('references')}
          label="References"
          icon={BookOpen}
        />
        <LibraryTabButton
          id="library-tab-policies"
          isActive={activeTab === 'policies'}
          onSelect={() => setActiveTab('policies')}
          label="Policies"
          icon={Scale}
        />
      </div>
      {activeTab === 'references' ? <ReferenceLibraryTab /> : <PolicyLibraryTab />}
    </section>
  );
}

function PageHeader() {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Admin</p>
        <h1 className="mt-1 text-xl font-bold text-slate-900">Reference Library</h1>
        <p className="mt-1 text-xs text-slate-500 font-medium">
          Manage shared syllabus, curriculum, and policy references used by evaluations.
        </p>
      </div>
      <Link
        to="/admin/ingest"
        className="inline-flex h-10 items-center gap-2 bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm"
      >
        <Upload className="size-4" />
        Upload reference
      </Link>
    </div>
  );
}

interface LibraryTabButtonProps {
  id: string;
  isActive: boolean;
  onSelect: () => void;
  label: string;
  icon: typeof BookOpen;
}

function LibraryTabButton({ id, isActive, onSelect, label, icon: Icon }: LibraryTabButtonProps) {
  return (
    <button
      id={id}
      role="tab"
      type="button"
      aria-selected={isActive}
      onClick={onSelect}
      className={cn(
        'inline-flex h-9 items-center gap-2 border-b-2 px-3 text-sm font-semibold uppercase tracking-wider transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] rounded-sm',
        isActive
          ? 'border-[#1b3b87] text-slate-900'
          : 'border-transparent text-slate-500 hover:border-slate-200 hover:text-slate-700',
      )}
    >
      <Icon className="size-4" aria-hidden="true" />
      {label}
    </button>
  );
}

function ReferenceLibraryTab() {
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

function PolicyLibraryTab() {
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
          className="inline-flex h-10 items-center gap-2 border border-slate-200 bg-white px-3 text-sm font-semibold uppercase tracking-wide text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 rounded-sm"
          aria-label="Refresh policy list"
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
            <Scale className="mx-auto size-8 text-slate-300" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-slate-600">No policy documents found.</p>
            <p className="mt-1 text-xs font-medium text-slate-500">
              Upload a policy PDF with a recognized area to start the ITSO evidence library.
            </p>
            <Link
              to="/admin/ingest"
              className="mt-4 inline-flex h-10 items-center gap-2 bg-[#1b3b87] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm"
            >
              <Upload className="size-4" />
              Upload policy
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse border-spacing-0">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4 font-semibold text-slate-500">Title</th>
                  <th className="py-3 px-4 font-semibold text-slate-500">Policy area</th>
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

interface ReferenceRowProps {
  item: ReferenceLibraryItem;
  isBusy: boolean;
  isDeleting: boolean;
  isRebuilding: boolean;
  onPreview: () => void;
  onRebuild: () => void;
  onDelete: () => void;
}

function ReferenceRow({
  item,
  isBusy,
  isDeleting,
  isRebuilding,
  onPreview,
  onRebuild,
  onDelete,
}: ReferenceRowProps) {
  const canRebuild = item.chunkCount > 0 && !item.chromaAvailable;

  return (
    <tr className="hover:bg-slate-50/50">
      <td className="py-3 px-4 align-top">
        <p
          className="text-sm font-semibold text-slate-900 truncate max-w-[16rem]"
          title={item.title}
        >
          {item.title}
        </p>
        {item.courseTitle ? (
          <p className="text-xs font-medium text-slate-500 truncate max-w-[16rem]">
            {item.courseTitle}
          </p>
        ) : null}
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-700">
          {referenceTypeLabels[item.sourceType] ?? item.sourceType}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-600">{item.courseCode ?? '—'}</span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-600">{item.academicYear ?? '—'}</span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-600 truncate max-w-[10rem] block">
          {item.lessonTitle ?? '—'}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider',
            processingStatusClass(item.processingStatus),
          )}
        >
          {item.processingStatus}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold',
            healthBadgeClass(item.fileExists),
          )}
        >
          {item.fileExists ? 'Found' : 'Missing'}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold tabular-nums',
            healthBadgeClass(item.chunkCount > 0),
          )}
        >
          {item.chunkCount}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold',
            healthBadgeClass(item.chromaAvailable),
          )}
        >
          {item.chromaAvailable ? 'Indexed' : 'Not indexed'}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-600">{formatDate(item.uploadedAt)}</span>
      </td>
      <td className="py-3 px-4 align-top text-right">
        <RowActionButtons
          canRebuild={canRebuild}
          isBusy={isBusy}
          isDeleting={isDeleting}
          isRebuilding={isRebuilding}
          rebuildTooltip={
            item.chromaAvailable
              ? 'Chroma vectors already present'
              : item.chunkCount === 0
                ? 'No chunks available to rebuild'
                : 'Rebuild Chroma vectors from stored chunks'
          }
          onPreview={onPreview}
          onRebuild={onRebuild}
          onDelete={onDelete}
        />
      </td>
    </tr>
  );
}

interface PolicyRowProps {
  item: PolicyLibraryItem;
  isBusy: boolean;
  isDeleting: boolean;
  isRebuilding: boolean;
  onPreview: () => void;
  onRebuild: () => void;
  onDelete: () => void;
}

function PolicyRow({
  item,
  isBusy,
  isDeleting,
  isRebuilding,
  onPreview,
  onRebuild,
  onDelete,
}: PolicyRowProps) {
  const canRebuild = item.chunkCount > 0 && !item.chromaAvailable;
  const areaLabel = isPolicyArea(item.policyArea)
    ? policyAreaLabelMap[item.policyArea]
    : (item.policyArea ?? '—');

  return (
    <tr className="hover:bg-slate-50/50">
      <td className="py-3 px-4 align-top">
        <p
          className="text-sm font-semibold text-slate-900 truncate max-w-[18rem]"
          title={item.title}
        >
          {item.title}
        </p>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="inline-flex items-center rounded-sm border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-slate-700">
          {areaLabel}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider',
            processingStatusClass(item.processingStatus),
          )}
        >
          {item.processingStatus}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold',
            healthBadgeClass(item.fileExists),
          )}
        >
          {item.fileExists ? 'Found' : 'Missing'}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold tabular-nums',
            healthBadgeClass(item.chunkCount > 0),
          )}
        >
          {item.chunkCount}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold',
            healthBadgeClass(item.chromaAvailable),
          )}
        >
          {item.chromaAvailable ? 'Indexed' : 'Not indexed'}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-600">{formatDate(item.uploadedAt)}</span>
      </td>
      <td className="py-3 px-4 align-top text-right">
        <RowActionButtons
          canRebuild={canRebuild}
          isBusy={isBusy}
          isDeleting={isDeleting}
          isRebuilding={isRebuilding}
          rebuildTooltip={
            item.chromaAvailable
              ? 'Chroma vectors already present'
              : item.chunkCount === 0
                ? 'No chunks available to rebuild'
                : 'Rebuild Chroma vectors from stored policy chunks'
          }
          onPreview={onPreview}
          onRebuild={onRebuild}
          onDelete={onDelete}
        />
      </td>
    </tr>
  );
}

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

function RowActionButtons({
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

interface ReferenceDeleteModalProps {
  item: ReferenceLibraryItem;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function ReferenceDeleteModal({
  item,
  isDeleting,
  onConfirm,
  onCancel,
}: ReferenceDeleteModalProps) {
  return (
    <DeleteModal
      title="Delete reference?"
      body={
        <>
          <p className="mt-1 text-sm font-medium text-slate-600">
            This will permanently remove{' '}
            <span className="font-semibold text-slate-900">{item.title}</span> and all stored
            chunks, embeddings, and the local PDF file.
          </p>
          {item.embeddingReady ? (
            <p className="mt-2 text-xs font-semibold text-[#b91c1c]">
              This reference is currently ready for evaluations. Deleting it may break linked
              evaluation jobs.
            </p>
          ) : null}
        </>
      }
      confirmLabel="Delete reference"
      isDeleting={isDeleting}
      onConfirm={onConfirm}
      onCancel={onCancel}
    />
  );
}

interface PolicyDeleteModalProps {
  item: PolicyLibraryItem;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function PolicyDeleteModal({ item, isDeleting, onConfirm, onCancel }: PolicyDeleteModalProps) {
  const areaLabel = isPolicyArea(item.policyArea)
    ? policyAreaLabelMap[item.policyArea]
    : (item.policyArea ?? 'unclassified');

  return (
    <DeleteModal
      title="Delete policy?"
      body={
        <>
          <p className="mt-1 text-sm font-medium text-slate-600">
            This will permanently remove the policy{' '}
            <span className="font-semibold text-slate-900">{item.title}</span> and all stored
            chunks, embeddings, and the local PDF file.
          </p>
          <p className="mt-2 text-xs font-semibold text-slate-500">
            Policy area: <span className="text-slate-700">{areaLabel}</span>. Historical ITSO
            results retain only hash-level audit evidence after deletion.
          </p>
        </>
      }
      confirmLabel="Delete policy"
      isDeleting={isDeleting}
      onConfirm={onConfirm}
      onCancel={onCancel}
    />
  );
}

interface DeleteModalProps {
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function DeleteModal({
  title,
  body,
  confirmLabel,
  isDeleting,
  onConfirm,
  onCancel,
}: DeleteModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
    >
      <div className="w-full max-w-md border border-slate-200 bg-white p-6 rounded-sm">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-sm border border-[#f2c811]/40 bg-[#f2c811]/15 text-[#1e293b]">
            <AlertTriangle className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 id="delete-dialog-title" className="text-base font-bold text-slate-900">
              {title}
            </h3>
            {body}
          </div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isDeleting}
            className="inline-flex h-10 items-center justify-center border border-slate-200 bg-white px-4 text-sm font-semibold uppercase tracking-wide text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50 rounded-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="inline-flex h-10 items-center justify-center bg-[#b91c1c] px-4 text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-[#b91c1c]/90 focus:outline-none focus:ring-2 focus:ring-[#b91c1c] disabled:opacity-50 rounded-sm"
          >
            {isDeleting ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" />
                Deleting...
              </span>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
