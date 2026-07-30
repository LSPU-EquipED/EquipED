import type { ReactNode } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import type { PolicyLibraryItem, ReferenceLibraryItem } from '../types';
import { isPolicyArea, policyAreaLabelMap } from '../utils/helpers';

interface DeleteModalProps {
  title: string;
  body: ReactNode;
  confirmLabel: string;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteModal({
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

interface ReferenceDeleteModalProps {
  item: ReferenceLibraryItem;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ReferenceDeleteModal({
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

export function PolicyDeleteModal({
  item,
  isDeleting,
  onConfirm,
  onCancel,
}: PolicyDeleteModalProps) {
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
