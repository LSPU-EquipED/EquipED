import { useState } from 'react';
import { Spinner, X } from '@phosphor-icons/react';
import { getRubricOperationError } from '../hooks/useRubrics';
import type { RubricDomain } from '../types';

interface DomainModalProps {
  isOpen: boolean;
  onClose: () => void;
  domain?: RubricDomain | null;
  onSave: (data: { code: string; title: string }) => Promise<void> | void;
  isPending: boolean;
  error?: unknown;
}

function DomainModalContent({
  onClose,
  domain,
  onSave,
  isPending,
  error,
}: Omit<DomainModalProps, 'isOpen'>) {
  const isEditing = Boolean(domain);

  const [code, setCode] = useState(domain?.code ?? '');
  const [title, setTitle] = useState(domain?.title ?? '');
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    const cleanCode = code.trim().toUpperCase();
    const cleanTitle = title.trim();

    if (!cleanCode) {
      setLocalError('Domain code is required (e.g. OP, GAD, IP).');
      return;
    }
    if (!cleanTitle) {
      setLocalError('Domain title is required.');
      return;
    }

    try {
      await onSave({ code: cleanCode, title: cleanTitle });
    } catch {
      // Handled by query/parent
    }
  };

  const errorMessage = localError || (error ? getRubricOperationError(error) : null);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="domain-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-md rounded-sm border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border p-4 bg-surface-subtle">
          <h2
            id="domain-modal-title"
            className="text-sm font-bold uppercase tracking-wider text-text"
          >
            {isEditing ? 'Edit Domain' : 'Add New Domain'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="inline-flex size-8 items-center justify-center rounded-sm text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close domain dialog"
          >
            <X className="size-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 grid gap-4">
          {errorMessage && (
            <div
              role="alert"
              className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive"
            >
              {errorMessage}
            </div>
          )}

          <div>
            <label
              htmlFor="domain-code"
              className="block text-xs font-bold uppercase tracking-wider text-text"
            >
              Domain Code <span className="text-destructive">*</span>
            </label>
            <input
              id="domain-code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              disabled={isPending}
              placeholder="e.g. OP"
              maxLength={50}
              className="mt-1 w-full h-8 rounded-sm border border-input bg-surface px-2.5 text-xs font-bold text-text uppercase focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label
              htmlFor="domain-title"
              className="block text-xs font-bold uppercase tracking-wider text-text"
            >
              Domain Title <span className="text-destructive">*</span>
            </label>
            <input
              id="domain-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isPending}
              placeholder="e.g. Organization and Presentation"
              maxLength={200}
              className="mt-1 w-full h-8 rounded-sm border border-input bg-surface px-2.5 text-xs font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-border pt-4 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="h-9 px-3 rounded-sm border border-border bg-surface text-xs font-bold uppercase tracking-wider text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="inline-flex h-9 items-center justify-center gap-1.5 px-4 rounded-sm bg-primary text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              {isPending && <Spinner className="size-3.5 animate-spin" />}
              {isEditing ? 'Save Changes' : 'Add Domain'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function DomainModal(props: DomainModalProps) {
  if (!props.isOpen) return null;

  return <DomainModalContent key={props.domain?.rubric_domain_id || 'new'} {...props} />;
}
