import { GitCommit } from '@phosphor-icons/react';
import type { UseQueryResult } from '@tanstack/react-query';
import { Skeleton } from '@equiped/ui';
import type { PromptVersionItem, PromptVersionListResponse } from '../types';
import { PromptVersionEntry } from './PromptVersionEntry';

type PromptVersionHistoryProps = {
  history: UseQueryResult<PromptVersionListResponse>;
  disabled?: boolean;
  onSelectVersion: (version: PromptVersionItem) => void;
  onRevertVersion: (version: PromptVersionItem) => void;
};

export function PromptVersionHistory({
  history,
  disabled,
  onSelectVersion,
  onRevertVersion,
}: PromptVersionHistoryProps) {
  const { data, isLoading, isError } = history;
  const versions = data?.versions ?? [];

  return (
    <section
      aria-labelledby="prompt-history-heading"
      className="overflow-hidden rounded-md border border-border bg-surface"
    >
      <header className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <h2 id="prompt-history-heading" className="text-base font-semibold text-text">
          Version history
        </h2>
        {!isLoading && !isError ? (
          <span className="text-xs tabular-nums text-text-muted">
            {versions.length} {versions.length === 1 ? 'revision' : 'revisions'}
          </span>
        ) : null}
      </header>
      <div className="max-h-[44rem] overflow-y-auto">
        {isLoading ? (
          <div
            role="status"
            aria-label="Loading prompt revisions"
            className="divide-y divide-border"
          >
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="space-y-3 p-5">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-4/5" />
                <Skeleton className="h-10 w-40" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <p role="alert" className="p-5 text-sm text-destructive">
            Version history is unavailable. Retry from the editor.
          </p>
        ) : versions.length === 0 ? (
          <div className="space-y-2 px-5 py-10 text-center">
            <GitCommit className="mx-auto size-6 text-text-muted" aria-hidden="true" />
            <p className="text-sm font-medium text-text">No revisions yet</p>
            <p className="text-xs text-text-muted">Save a prompt to create the first version.</p>
          </div>
        ) : (
          <ol className="divide-y divide-border">
            {versions.map((version) => (
              <PromptVersionEntry
                key={version.version_id}
                version={version}
                disabled={disabled}
                onSelectVersion={onSelectVersion}
                onRevertVersion={onRevertVersion}
              />
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
