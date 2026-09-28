import { useState } from 'react';
import { cn, Skeleton } from '@equiped/ui';
import { criterionKey } from '../utils/helpers';
import type { ModelValidationFormState } from '../hooks/useModelValidationFormState';
import { CriterionScoreField } from './CriterionScoreField';

export function ValidationBenchmarkScores({
  form,
}: {
  form: Pick<
    ModelValidationFormState,
    | 'registerScoreInput'
    | 'expectedScores'
    | 'setExpectedScores'
    | 'criterionCatalog'
    | 'criterionDefinitions'
    | 'handleScoreKeyDown'
  >;
}) {
  const { expectedScores, criterionCatalog, criterionDefinitions } = form;
  const [activeAgentTab, setActiveAgentTab] = useState<string>('sme');

  // The default tab state is 'sme'; with a single-agent target that agent may
  // not be in scope, so fall back to the first agent that is.
  const visibleAgentId = criterionDefinitions.some((agent) => agent.agent_id === activeAgentTab)
    ? activeAgentTab
    : criterionDefinitions[0]?.agent_id;

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <div className="border-b border-border px-5 py-4">
        <p className="text-xs font-semibold text-primary">Benchmark reference</p>
        <h3 className="mt-1 text-lg font-semibold text-text">Expected criterion scores</h3>
        <p className="mt-1 text-sm leading-relaxed text-text-muted">
          Select an evaluator agent and enter the human score for each active criterion.
        </p>
      </div>

      {/* Agent Sub-Tabs */}
      <div className="flex flex-wrap gap-1.5 border-b border-border bg-surface-subtle/50 p-3">
        {criterionDefinitions.map((agent) => {
          const isTabActive = visibleAgentId === agent.agent_id;
          const criteriaList = agent.domains?.length
            ? agent.domains.flatMap((d) => d.criteria)
            : (agent.criteria ?? []);
          const agentScoreCount = criteriaList.filter((c) => {
            const k = criterionKey(agent.agent_id, c.rubric_criterion_id || c.criterion_id!);
            return expectedScores[k] && /^[1-4]$/.test(expectedScores[k]);
          }).length;
          const isComplete = criteriaList.length > 0 && agentScoreCount === criteriaList.length;

          return (
            <button
              key={agent.agent_id}
              type="button"
              onClick={() => setActiveAgentTab(agent.agent_id)}
              className={cn(
                'flex min-h-10 items-center gap-2 rounded-sm border px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isTabActive
                  ? 'border-primary bg-primary text-primary-foreground font-bold shadow-2xs'
                  : 'border-border bg-surface text-text hover:bg-surface-subtle',
              )}
            >
              <span>{agent.agent_name}</span>
              <span
                className={cn(
                  'rounded-xs px-1.5 py-0.2 text-[10px] font-mono tabular-nums font-bold border',
                  isTabActive
                    ? 'bg-primary-foreground/20 text-primary-foreground border-transparent'
                    : isComplete
                      ? 'bg-success-soft text-success border-success/30'
                      : 'bg-surface-subtle text-text-muted border-border',
                )}
              >
                {agentScoreCount}/{criteriaList.length}
              </span>
            </button>
          );
        })}
      </div>

      {/* Criteria Panels per Agent */}
      <div className="p-5">
        {criterionCatalog.isLoading ? (
          <div role="status" aria-label="Loading active rubric criteria" className="space-y-3">
            {Array.from({ length: 5 }).map((_, index) => (
              <div
                key={index}
                className="space-y-2 rounded-sm border border-border bg-surface-subtle p-3"
              >
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="h-3 w-full" />
              </div>
            ))}
          </div>
        ) : criterionCatalog.isError ? (
          <div className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-sm font-semibold text-destructive">
            <p>Unable to load the active rubric criteria.</p>
            <button
              type="button"
              onClick={() => criterionCatalog.refetch()}
              className="mt-2 text-xs font-bold uppercase tracking-wider underline hover:text-destructive/80 cursor-pointer"
            >
              Retry loading criteria
            </button>
          </div>
        ) : criterionDefinitions.length === 0 ||
          criterionDefinitions.some((agent) => {
            const count = agent.domains?.length
              ? agent.domains.reduce((sum, d) => sum + d.criteria.length, 0)
              : agent.criteria.length;
            return count === 0;
          }) ? (
          <p className="rounded-sm border border-warning/40 bg-warning-soft p-4 text-sm font-semibold text-text">
            No active rubric criteria are available for SME, GAD, or ITSO. Activate the evaluator
            agent rubrics first.
          </p>
        ) : (
          criterionDefinitions.map((agent) => {
            const isVisible = visibleAgentId === agent.agent_id;
            const hasDomains = agent.domains && agent.domains.length > 0;

            return (
              <div key={agent.agent_id} className={cn(isVisible ? 'space-y-4' : 'hidden')}>
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className="text-xs font-semibold text-text-muted">
                    Criteria in this run
                  </span>
                  <span className="rounded-xs border border-border bg-surface-subtle px-2 py-0.5 text-[11px] font-mono font-semibold text-text-muted tabular-nums">
                    Rubric v{agent.rubric_version}
                  </span>
                </div>

                {hasDomains ? (
                  <div className="space-y-3.5">
                    {agent.domains.map((domain) => {
                      const domainScoreCount = domain.criteria.filter((criterion) => {
                        const score =
                          expectedScores[
                            criterionKey(agent.agent_id, criterion.rubric_criterion_id)
                          ];
                        return score && /^[1-4]$/.test(score);
                      }).length;

                      return (
                        <details
                          key={domain.rubric_domain_id}
                          open
                          className="overflow-hidden rounded-sm border border-border"
                        >
                          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 bg-surface-subtle px-4 py-3 text-xs font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset">
                            <span>
                              {domain.code} · {domain.title}
                            </span>
                            <span className="shrink-0 font-mono text-[11px] font-semibold tabular-nums text-text-muted">
                              {domainScoreCount}/{domain.criteria.length}
                            </span>
                          </summary>
                          <div className="divide-y divide-border">
                            {domain.criteria.map((criterion) => {
                              const key = criterionKey(
                                agent.agent_id,
                                criterion.rubric_criterion_id,
                              );

                              return (
                                <CriterionScoreField
                                  key={key}
                                  scoreKey={key}
                                  criterion={criterion}
                                  domainTitle={domain.title}
                                  form={form}
                                />
                              );
                            })}
                          </div>
                        </details>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-sm border border-border divide-y divide-border">
                    {agent.criteria.map((criterion) => {
                      const key = criterionKey(
                        agent.agent_id,
                        criterion.rubric_criterion_id || criterion.criterion_id!,
                      );

                      return (
                        <CriterionScoreField
                          key={key}
                          scoreKey={key}
                          criterion={criterion}
                          form={form}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
