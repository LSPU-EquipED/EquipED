import { useMemo } from 'react';
import {
  BookOpen,
  CaretDown,
  CaretRight,
  CheckCircle,
  Lightbulb,
  Scales,
  ShieldCheck,
  WarningCircle,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { cn } from '@/shared/components/utils';
import { formatScore, agentShortLabel } from '../utils/scoreHelpers';
import type { CriterionScoreItem, DomainScoreBlock, EvaluationResultsResponse } from '../types';

const AGENTS = [
  {
    id: 'sme',
    name: 'Subject Matter Expert',
    subtitle: 'Discipline accuracy & rigor',
    icon: Lightbulb,
  },
  {
    id: 'coordinator',
    name: 'Program Coordinator',
    subtitle: 'Curriculum & syllabus match',
    icon: BookOpen,
  },
  {
    id: 'gad',
    name: 'GAD Unit',
    subtitle: 'Gender & development',
    icon: Scales,
  },
  {
    id: 'itso',
    name: 'ITSO Compliance',
    subtitle: 'IP, citation & copyright',
    icon: ShieldCheck,
  },
] as const;

interface DomainCriteriaTreeProps {
  results: EvaluationResultsResponse | undefined;
  selectedAgentId: string;
  selectedCriterionId: string | null;
  onSelectCriterion: (agentId: string, criterionId: string) => void;
  isPartial?: boolean;
}

export function DomainCriteriaTree({
  results,
  selectedAgentId,
  selectedCriterionId,
  onSelectCriterion,
  isPartial,
}: DomainCriteriaTreeProps) {
  const domainScores = results?.domain_scores || {};

  return (
    <aside
      aria-label="Evaluation Domains & Criteria"
      className="flex flex-col h-full min-h-0 border-r border-border bg-surface"
    >
      {/* Sidebar Header */}
      <div className="border-b border-border bg-surface-subtle px-4 py-3 shrink-0">
        <h3 className="text-xs font-bold uppercase tracking-wider text-text">
          Review Domains ({AGENTS.length})
        </h3>
        <p className="text-[11px] text-text-muted mt-0.5">
          Select any criterion to inspect findings and quoted evidence.
        </p>
      </div>

      {/* Domain Tree List */}
      <div className="flex-1 overflow-y-auto divide-y divide-border">
        {AGENTS.map((agent) => {
          const Icon = agent.icon;
          const isSelectedAgent = agent.id === selectedAgentId;
          const isSkipped = isPartial && agent.id === 'coordinator';
          const domainBlock: DomainScoreBlock | undefined = domainScores[agent.id];
          const criteria = (domainBlock?.criteria || []).slice().sort((a, b) => {
            if (a.display_order != null && b.display_order != null) {
              return a.display_order - b.display_order;
            }
            return a.criterion_id.localeCompare(b.criterion_id, undefined, { numeric: true });
          });
          return (
            <div key={agent.id} className="bg-surface">
              {/* Domain Header Card */}
              <div
                className={cn(
                  'p-3.5 transition-colors cursor-pointer select-none flex items-start justify-between gap-2',
                  isSelectedAgent ? 'bg-surface-subtle' : 'hover:bg-surface-subtle/60',
                )}
                onClick={() => {
                  if (criteria.length > 0) {
                    onSelectCriterion(agent.id, criteria[0].criterion_id);
                  }
                }}
              >
                <div className="flex items-start gap-2.5 min-w-0">
                  <div
                    className={cn(
                      'flex size-7 items-center justify-center rounded-xs shrink-0 mt-0.5 border',
                      isSelectedAgent
                        ? 'bg-primary-soft text-primary border-primary/20'
                        : 'bg-surface-subtle text-text-muted border-border',
                    )}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                  </div>
                  <div className="min-w-0">
                    <span className="text-xs font-bold text-text truncate block">
                      {agent.name}
                    </span>
                    <span className="text-[10px] text-text-muted truncate block">
                      {agent.subtitle}
                    </span>
                  </div>
                </div>

                {/* Domain Score Badge */}
                <div className="shrink-0 flex items-center gap-1.5">
                  {isSkipped ? (
                    <Badge variant="warning">Skipped</Badge>
                  ) : domainBlock ? (
                    <span className="inline-flex items-center rounded-xs bg-surface-subtle border border-border px-2 py-0.5 text-xs font-bold text-text tabular-nums">
                      {formatScore(domainBlock.subtotal)} / {formatScore(domainBlock.max_score || 4)}
                    </span>
                  ) : (
                    <span className="text-[11px] text-text-muted font-medium">Pending</span>
                  )}
                  {isSelectedAgent ? (
                    <CaretDown className="size-3 text-text-muted" />
                  ) : (
                    <CaretRight className="size-3 text-text-muted" />
                  )}
                </div>
              </div>

              {/* Criteria List for Selected Domain */}
              {isSelectedAgent && criteria.length > 0 ? (
                <div className="divide-y divide-border/60 bg-surface-subtle/30 pl-4">
                  {criteria.map((criterion) => {
                    const isSelected = criterion.criterion_id === selectedCriterionId;
                    const isPassing = criterion.score >= 3.0;

                    return (
                      <button
                        key={criterion.criterion_id}
                        type="button"
                        onClick={() => onSelectCriterion(agent.id, criterion.criterion_id)}
                        className={cn(
                          'w-full text-left p-3 pr-4 flex items-start justify-between gap-3 transition-colors cursor-pointer select-none',
                          isSelected
                            ? 'bg-surface border-l-2 border-primary text-text shadow-xs'
                            : 'hover:bg-surface/80 text-text-muted border-l-2 border-transparent',
                        )}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-[11px] font-bold text-text-muted">
                              {criterion.criterion_id}
                            </span>
                            {criterion.is_ungrounded ? (
                              <Badge variant="warning">Ungrounded</Badge>
                            ) : null}
                          </div>
                          <p
                            className={cn(
                              'text-xs mt-0.5 line-clamp-2 leading-relaxed',
                              isSelected ? 'font-semibold text-text' : 'font-medium text-text-muted',
                            )}
                          >
                            {criterion.criterion_text}
                          </p>
                        </div>

                        {/* Score Chip */}
                        <span
                          className={cn(
                            'shrink-0 inline-flex items-center rounded-xs px-2 py-0.5 text-xs font-bold tabular-nums border',
                            isPassing
                              ? 'bg-success-soft text-success border-success/20'
                              : 'bg-warning-soft text-warning border-warning/20',
                          )}
                        >
                          {formatScore(criterion.score)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
