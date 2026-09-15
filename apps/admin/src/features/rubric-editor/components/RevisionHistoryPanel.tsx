import { CheckCircle, ClockCounterClockwise, Plus, Power, Spinner, Trash } from '@phosphor-icons/react';
import type { RubricSet } from '../types';

interface RevisionHistoryPanelProps {
  agentId: string;
  agentLabel: string;
  revisions: RubricSet[];
  activePointerId?: string | null;
  selectedRevisionId?: string | null;
  onSelectRevision: (revisionId: string) => void;
  onCreateDraft: () => void;
  onDeleteDraft: (rubricSetId: string) => void;
  onActivateRevision: (rubricSetId: string) => void;
  onRequestRollback?: (revision: RubricSet) => void;
  onRetireRevision: (rubricSetId: string) => void;
  isActionPending?: boolean;
}

export function RevisionHistoryPanel({
  agentLabel,
  revisions,
  activePointerId,
  selectedRevisionId,
  onSelectRevision,
  onCreateDraft,
  onDeleteDraft,
  onActivateRevision,
  onRequestRollback,
  onRetireRevision,
  isActionPending = false,
}: RevisionHistoryPanelProps) {
  const hasDraft = revisions.some((r) => r.status === 'draft');

  return (
    <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4 bg-surface-subtle">
        <div>
          <div className="flex items-center gap-2">
            <ClockCounterClockwise className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-text">
              Revision History
            </h2>
          </div>
          <p className="text-[11px] text-text-muted font-medium">Revisions for {agentLabel}</p>
        </div>

        {!hasDraft && (
          <button
            type="button"
            onClick={onCreateDraft}
            disabled={isActionPending}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-sm bg-primary px-2.5 text-xs font-semibold text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 cursor-pointer transition-colors"
          >
            {isActionPending ? (
              <Spinner className="size-3.5 animate-spin" />
            ) : (
              <Plus className="size-3.5" />
            )}
            <span>Create Draft</span>
          </button>
        )}
      </div>

      <div className="p-4 grid gap-3 max-h-[38rem] overflow-y-auto">
        {revisions.length === 0 ? (
          <p className="text-xs font-medium text-text-muted py-6 text-center">
            No revisions found for this agent.
          </p>
        ) : (
          revisions.map((rev) => {
            const isSelected = rev.rubric_set_id === selectedRevisionId;
            const isActive = rev.rubric_set_id === activePointerId || Boolean(rev.is_active);
            const isDraft = rev.status === 'draft';
            const isPublished = rev.status === 'published';

            return (
              <div
                key={rev.rubric_set_id}
                className={`rounded-sm border p-3.5 transition-colors ${
                  isSelected
                    ? 'border-primary bg-surface-subtle/80'
                    : 'border-border bg-surface hover:border-border-strong'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-text tabular-nums">
                      v{rev.version_number}
                    </span>
                    {isActive && (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-success-soft px-1.5 py-0.5 text-[10px] font-semibold text-success border border-success/20">
                        <CheckCircle className="size-3" />
                        Active Pointer
                      </span>
                    )}
                  </div>

                  <span
                    className={`rounded-xs px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                      isDraft
                        ? 'bg-warning-soft text-warning border border-warning/20'
                        : isPublished
                          ? 'bg-primary-soft text-primary border border-primary/20'
                          : 'bg-surface-subtle text-text-muted border border-border'
                    }`}
                  >
                    {rev.status}
                  </span>
                </div>

                <div className="mt-2 text-[11px] text-text-muted grid gap-0.5">
                  <p className="font-semibold text-text">{rev.name}</p>
                  <p className="text-text-muted tabular-nums">
                    {rev.domains.length} domain(s) ·{' '}
                    {rev.domains.reduce((acc, d) => acc + d.criteria.length, 0)} criteria
                  </p>
                  {rev.published_at && (
                    <p className="text-[10px] text-text-muted tabular-nums">
                      Published: {new Date(rev.published_at).toLocaleDateString()}
                    </p>
                  )}
                  {rev.retired_at && (
                    <p className="text-[10px] text-text-muted tabular-nums">
                      Retired: {new Date(rev.retired_at).toLocaleDateString()}
                    </p>
                  )}
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-border pt-2.5">
                  {!isSelected && (
                    <button
                      type="button"
                      onClick={() => onSelectRevision(rev.rubric_set_id)}
                      className="h-7 px-2.5 rounded-xs border border-border bg-surface text-xs font-semibold text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer transition-colors"
                    >
                      View
                    </button>
                  )}

                  {isDraft && (
                    <button
                      type="button"
                      onClick={() => onDeleteDraft(rev.rubric_set_id)}
                      disabled={isActionPending}
                      className="inline-flex h-7 items-center gap-1 px-2.5 rounded-xs border border-destructive/30 text-destructive hover:bg-destructive-soft text-xs font-semibold focus-visible:outline-none disabled:opacity-50 cursor-pointer transition-colors"
                      aria-label={`Delete draft revision v${rev.version_number}`}
                    >
                      <Trash className="size-3" />
                      <span>Delete Draft</span>
                    </button>
                  )}

                  {isPublished && !isActive && (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          if (onRequestRollback) {
                            onRequestRollback(rev);
                          } else {
                            onActivateRevision(rev.rubric_set_id);
                          }
                        }}
                        disabled={isActionPending}
                        className="inline-flex h-7 items-center gap-1 px-2.5 rounded-xs bg-primary text-primary-foreground hover:bg-primary-strong text-xs font-semibold focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50 cursor-pointer transition-colors"
                      >
                        <Power className="size-3" />
                        <span>Activate (Rollback)</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onRetireRevision(rev.rubric_set_id)}
                        disabled={isActionPending}
                        className="h-7 px-2.5 rounded-xs border border-border text-text hover:bg-surface-subtle text-xs font-semibold focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50 cursor-pointer transition-colors"
                      >
                        <span>Retire</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
