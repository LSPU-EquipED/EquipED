import { Link } from '@tanstack/react-router';
import { CaretRight, Spinner } from '@phosphor-icons/react';
import { isTargetAgent, TARGET_AGENT_META } from '@equiped/types';
import type { HomeEvaluationItem } from '../types';

export interface FacultyActiveEvaluationBannerProps {
  evaluation: HomeEvaluationItem | null;
}

export function FacultyActiveEvaluationBanner({ evaluation }: FacultyActiveEvaluationBannerProps) {
  if (!evaluation) return null;

  const targetAgent = evaluation.target_agent;
  const isAllAgentEvaluation = targetAgent === 'all';
  const agentKey = isTargetAgent(targetAgent) ? targetAgent : 'sme';
  const agentMeta = TARGET_AGENT_META[agentKey];

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-md border border-primary/25 bg-primary-soft/30 px-4 sm:px-5 py-3 text-xs text-text shadow-none"
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex size-7.5 shrink-0 items-center justify-center rounded-xs border border-primary/30 bg-primary-soft text-primary">
          <Spinner className="size-4 animate-spin" aria-hidden="true" />
        </div>
        <div className="min-w-0 space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="font-bold text-primary">Active Evaluation in Progress</span>
            <span className="rounded-xs bg-primary/10 border border-primary/20 px-1.5 py-0.2 text-[11px] font-semibold text-primary font-mono">
              {isAllAgentEvaluation ? 'All' : agentMeta.shortLabel}
            </span>
          </div>
          <p className="truncate text-text font-medium">
            {evaluation.document_title || 'Untitled SLM'}
            <span className="text-text-muted ml-2 font-normal font-mono text-[11px]">
              ({evaluation.evaluation_id.slice(0, 8)})
            </span>
          </p>
        </div>
      </div>

      {!isAllAgentEvaluation ? (
        <Link
          to="/specialists/$agentId/$documentId"
          params={{ agentId: agentKey, documentId: evaluation.document_id }}
          className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-primary/30 bg-surface px-3 text-xs font-semibold text-primary hover:bg-primary-soft/40 transition-colors shrink-0"
        >
          <span>Open Specialist Scoreboard</span>
          <CaretRight className="size-3.5" aria-hidden="true" />
        </Link>
      ) : (
        <Link
          to="/evaluations/$id"
          params={{ id: evaluation.evaluation_id }}
          className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-primary/30 bg-surface px-3 text-xs font-semibold text-primary hover:bg-primary-soft/40 transition-colors shrink-0"
        >
          <span>Open Evaluation Scorecard</span>
          <CaretRight className="size-3.5" aria-hidden="true" />
        </Link>
      )}
    </div>
  );
}
