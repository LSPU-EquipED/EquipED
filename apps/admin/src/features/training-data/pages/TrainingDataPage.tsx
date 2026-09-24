import { useNavigate, useParams } from '@tanstack/react-router';
import { GraduationCap } from '@phosphor-icons/react';
import { TYPOGRAPHY, cn, PageContainer } from '@equiped/ui';
import { AdapterListTable } from '../components/AdapterListTable';
import { DatasetReadinessCard } from '../components/DatasetReadinessCard';
import { TrainingJobsPanel } from '../components/TrainingJobsPanel';
import { DEFAULT_TRAINING_AGENT_ID, TRAINING_AGENTS } from '../trainingAgents';

export function TrainingDataPage() {
  const { agentId } = useParams({ strict: false }) as { agentId?: string };
  const navigate = useNavigate();
  const activeAgent = agentId ?? DEFAULT_TRAINING_AGENT_ID;
  const activeAgentMeta =
    TRAINING_AGENTS.find((a) => a.id === activeAgent) ?? TRAINING_AGENTS[0];

  return (
    <PageContainer as="section" key={activeAgent}>
      <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
        <nav
          className="flex flex-wrap gap-1 px-4 pt-2 border-b border-border bg-surface-subtle"
          aria-label="Specialist Agents"
        >
          {TRAINING_AGENTS.map((agent) => {
            const isTabSelected = activeAgent === agent.id;
            return (
              <button
                key={agent.id}
                type="button"
                role="tab"
                aria-selected={isTabSelected}
                onClick={() => {
                  void navigate({
                    to: '/admin/training-data/$agentId',
                    params: { agentId: agent.id },
                  });
                }}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-xs font-semibold transition-colors border-b-2 cursor-pointer select-none',
                  isTabSelected
                    ? 'border-primary text-primary font-bold bg-surface'
                    : 'border-transparent text-text-muted hover:text-text hover:border-border',
                )}
              >
                <GraduationCap className="size-4" />
                <span>{agent.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="space-y-1">
        <h1 className={TYPOGRAPHY.headingLg}>{activeAgentMeta.label} — Training Data</h1>
        <p className="text-sm text-text-muted">
          Freeze a DPO dataset snapshot, hand it to a Colab notebook, and track adapters trained
          from it.
        </p>
      </div>

      <DatasetReadinessCard agentId={activeAgent} />
      <TrainingJobsPanel agentId={activeAgent} />
      <AdapterListTable agentId={activeAgent} />
    </PageContainer>
  );
}
