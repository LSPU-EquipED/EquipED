import { ArrowCounterClockwise, ClockCounterClockwise, GitCommit } from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { usePromptVersions } from '../hooks/usePromptVersions';
import type { PromptVersionItem } from '../types';

interface PromptVersionHistoryProps {
  agentId: string;
  agentLabel: string;
  onSelectVersion?: (version: PromptVersionItem) => void;
  onRevertVersion?: (version: PromptVersionItem) => void;
}

export function PromptVersionHistory({
  agentId,
  agentLabel,
  onSelectVersion,
  onRevertVersion,
}: PromptVersionHistoryProps) {
  const { data, isLoading, isError } = usePromptVersions(agentId);
  const versions = data?.versions ?? [];

  return (
    <div className="rounded-md border border-border bg-surface overflow-hidden shadow-none flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border p-4 sm:p-5 bg-surface-subtle flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ClockCounterClockwise className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-text">
              Version History
            </h2>
          </div>
          <p className="text-[11px] text-text-muted mt-0.5 font-medium">
            Directives for {agentLabel}
          </p>
        </div>
        <span className="text-[11px] font-mono font-semibold text-text-muted rounded-xs bg-surface border border-border px-2 py-0.5 tabular-nums">
          {versions.length} revisions
        </span>
      </div>

      {/* History List */}
      <div className="p-4 sm:p-5 space-y-3.5 max-h-[44rem] overflow-y-auto flex-1">
        {isLoading ? (
          <div role="status" aria-label="Loading prompt revisions" className="space-y-3.5">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="space-y-3 rounded-sm border border-border bg-surface p-4">
                <div className="flex items-center justify-between gap-3">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-5 w-16" />
                </div>
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-4/5" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <p className="text-xs font-semibold text-destructive py-8 text-center bg-destructive-soft rounded-sm p-3">
            Failed to load prompt version history.
          </p>
        ) : versions.length === 0 ? (
          <div className="py-12 text-center text-text-muted space-y-1">
            <GitCommit className="size-6 text-text-muted/40 mx-auto" aria-hidden="true" />
            <p className="text-xs font-semibold text-text">No prompt revisions yet.</p>
            <p className="text-[11px] text-text-muted">Save the first directive to record version 1.</p>
          </div>
        ) : (
          versions.map((version) => {
            const isActive = version.is_active;

            return (
              <div
                key={version.version_id}
                className={`rounded-sm border p-4 text-xs space-y-2.5 transition-colors ${
                  isActive
                    ? 'border-primary/40 bg-primary-soft/20 shadow-2xs'
                    : 'border-border bg-surface hover:border-border-strong'
                }`}
              >
                {/* Title & Status Bar */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-text text-xs tabular-nums">
                      v{version.version_number}
                    </span>
                    <Badge variant={isActive ? 'success' : 'neutral'} withDot>
                      {isActive ? 'Active' : 'Archived'}
                    </Badge>
                  </div>

                  {/* Actions for Archived Versions */}
                  {!isActive ? (
                    <div className="flex items-center gap-1.5">
                      {onSelectVersion && (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => onSelectVersion(version)}
                          className="h-6.5 px-2 text-[11px] font-semibold"
                          title="Load text into editor for editing"
                        >
                          <span>Load</span>
                        </Button>
                      )}
                      {onRevertVersion && (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => onRevertVersion(version)}
                          className="h-6.5 px-2 text-[11px] font-semibold text-primary hover:text-primary-strong gap-1"
                          title="Rollback active prompt to this version"
                        >
                          <ArrowCounterClockwise className="size-3" />
                          <span>Revert</span>
                        </Button>
                      )}
                    </div>
                  ) : (
                    <span className="text-[11px] text-success font-semibold">Live in Evaluations</span>
                  )}
                </div>

                {/* Prompt Preview Snippet */}
                <p className="whitespace-pre-wrap text-text font-mono text-[11px] leading-relaxed max-h-24 overflow-y-auto bg-surface p-2.5 rounded-xs border border-border/80">
                  {version.prompt_text}
                </p>

                {/* Motivation / Changelog */}
                {version.motivation ? (
                  <p className="text-[11px] text-text-muted leading-relaxed italic border-l-2 border-primary/30 pl-2">
                    &ldquo;{version.motivation}&rdquo;
                  </p>
                ) : null}

                {/* Attribution & Date */}
                <div className="flex items-center justify-between text-[10px] font-medium text-text-muted tabular-nums pt-1 border-t border-border/60">
                  <span>Author: {version.updated_by || 'System'}</span>
                  <span>{new Date(version.created_at).toLocaleString()}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
