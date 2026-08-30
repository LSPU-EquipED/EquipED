import { CheckCircle, History, Loader2, Plus, Power, Trash2 } from 'lucide-react';
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
  onRetireRevision,
  isActionPending = false,
}: RevisionHistoryPanelProps) {
  const hasDraft = revisions.some((r) => r.status === 'draft');

  return (
    <div className="rounded-sm border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4 bg-slate-50">
        <div>
          <div className="flex items-center gap-2">
            <History className="size-4 text-slate-500" aria-hidden="true" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-800">
              Revision History
            </h2>
          </div>
          <p className="text-[11px] text-slate-500 font-medium">Revisions for {agentLabel}</p>
        </div>

        {!hasDraft && (
          <button
            type="button"
            onClick={onCreateDraft}
            disabled={isActionPending}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-sm bg-[#1b3b87] px-2.5 text-[11px] font-bold uppercase tracking-wider text-white hover:bg-[#1b3b87]/90 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-50"
          >
            {isActionPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Plus className="size-3.5" />
            )}
            Create Draft
          </button>
        )}
      </div>

      <div className="p-4 grid gap-3 max-h-[38rem] overflow-y-auto">
        {revisions.length === 0 ? (
          <p className="text-xs font-medium text-slate-500 py-4 text-center">
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
                className={`rounded-sm border p-3 transition-colors ${
                  isSelected
                    ? 'border-[#1b3b87] bg-slate-50/80 shadow-xs'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">v{rev.version_number}</span>
                    {isActive && (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-[#3b963e]/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#3b963e]">
                        <CheckCircle className="size-3" />
                        Active Pointer
                      </span>
                    )}
                  </div>

                  <span
                    className={`rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                      isDraft
                        ? 'bg-[#f2c811]/25 text-amber-900 border border-[#f2c811]/40'
                        : isPublished
                          ? 'bg-blue-50 text-[#1b3b87] border border-blue-200'
                          : 'bg-slate-100 text-slate-600 border border-slate-200'
                    }`}
                  >
                    {rev.status}
                  </span>
                </div>

                <div className="mt-2 text-[11px] text-slate-600 grid gap-0.5">
                  <p className="font-semibold text-slate-800">{rev.name}</p>
                  <p className="text-slate-500">
                    {rev.domains.length} domain(s) ·{' '}
                    {rev.domains.reduce((acc, d) => acc + d.criteria.length, 0)} criteria
                  </p>
                  {rev.published_at && (
                    <p className="text-[10px] text-slate-400">
                      Published: {new Date(rev.published_at).toLocaleDateString()}
                    </p>
                  )}
                  {rev.retired_at && (
                    <p className="text-[10px] text-slate-400">
                      Retired: {new Date(rev.retired_at).toLocaleDateString()}
                    </p>
                  )}
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-2">
                  {!isSelected && (
                    <button
                      type="button"
                      onClick={() => onSelectRevision(rev.rubric_set_id)}
                      className="h-7 px-2 rounded-sm border border-slate-200 bg-white text-[10px] font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-1 focus:ring-[#1b3b87]"
                    >
                      View
                    </button>
                  )}

                  {isDraft && (
                    <button
                      type="button"
                      onClick={() => onDeleteDraft(rev.rubric_set_id)}
                      disabled={isActionPending}
                      className="inline-flex h-7 items-center gap-1 px-2 rounded-sm border border-[#b91c1c]/30 text-[#b91c1c] hover:bg-[#b91c1c]/5 text-[10px] font-bold uppercase tracking-wider focus:outline-none disabled:opacity-50"
                      aria-label={`Delete draft revision v${rev.version_number}`}
                    >
                      <Trash2 className="size-3" />
                      Delete Draft
                    </button>
                  )}

                  {isPublished && !isActive && (
                    <>
                      <button
                        type="button"
                        onClick={() => onActivateRevision(rev.rubric_set_id)}
                        disabled={isActionPending}
                        className="inline-flex h-7 items-center gap-1 px-2 rounded-sm bg-[#1b3b87] text-white hover:bg-[#1b3b87]/90 text-[10px] font-bold uppercase tracking-wider focus:outline-none disabled:opacity-50"
                      >
                        <Power className="size-3" />
                        Activate (Rollback)
                      </button>
                      <button
                        type="button"
                        onClick={() => onRetireRevision(rev.rubric_set_id)}
                        disabled={isActionPending}
                        className="h-7 px-2 rounded-sm border border-slate-200 text-slate-600 hover:bg-slate-100 text-[10px] font-bold uppercase tracking-wider focus:outline-none disabled:opacity-50"
                      >
                        Retire
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
