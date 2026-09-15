import type { ReactNode } from 'react';
import { Spinner, Warning } from '@phosphor-icons/react';
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
    >
      <div className="w-full max-w-md border border-border bg-surface p-6 rounded-sm shadow-md">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-sm border border-warning/40 bg-warning-soft text-warning">
            <Warning className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 id="delete-dialog-title" className="text-base font-bold text-text">
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
            className="inline-flex h-10 items-center justify-center border border-border bg-surface px-4 text-sm font-semibold uppercase tracking-wide text-text transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 rounded-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="inline-flex h-10 items-center justify-center bg-destructive px-4 text-sm font-semibold uppercase tracking-wide text-destructive-foreground transition-colors hover:bg-destructive/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50 rounded-sm"
          >
            {isDeleting ? (
              <span className="inline-flex items-center gap-2">
                <Spinner className="size-4 animate-spin" />
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
          <p className="mt-1 text-sm font-medium text-text-muted">
            This will permanently remove{' '}
            <span className="font-semibold text-text">{item.title}</span> and all stored
            chunks, embeddings, and the local PDF file.
          </p>
          {item.embeddingReady ? (
            <p className="mt-2 text-xs font-semibold text-destructive">
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
          <p className="mt-1 text-sm font-medium text-text-muted">
            This will permanently remove the policy{' '}
            <span className="font-semibold text-text">{item.title}</span> and all stored
            chunks, embeddings, and the local PDF file.
          </p>
          <p className="mt-2 text-xs font-semibold text-text-muted">
            Policy area: <span className="text-text">{areaLabel}</span>. Historical ITSO
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
