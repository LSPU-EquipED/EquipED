import { useNavigate, useParams } from '@tanstack/react-router';
import { GraduationCap } from '@phosphor-icons/react';
import { TYPOGRAPHY, cn } from '@equiped/ui';
import { AdapterListTable } from '../components/AdapterListTable';
import { TrainingJobsPanel } from '../components/TrainingJobsPanel';

const AGENTS = [
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'gad', label: 'Gender & Development (GAD)' },
  { id: 'itso', label: 'Intellectual Property (ITSO)' },
] as const;

export function TrainingDataPage() {
  const { agentId } = useParams({ strict: false }) as { agentId?: string };
  const navigate = useNavigate();
  const activeAgent = agentId ?? 'coordinator';
  const activeAgentMeta = AGENTS.find((a) => a.id === activeAgent) ?? AGENTS[0];

  return (
    <section key={activeAgent} className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-8">
      <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
        <nav
          className="flex flex-wrap gap-1 px-4 pt-2 border-b border-border bg-surface-subtle"
          aria-label="Specialist Agents"
        >
          {AGENTS.map((agent) => {
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

      <TrainingJobsPanel agentId={activeAgent} />
      <AdapterListTable agentId={activeAgent} />
    </section>
  );
}
