import { useRef, type KeyboardEvent } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { cn, PageContainer } from '@equiped/ui';
import { TrainingDataWorkspace } from '../components/TrainingDataWorkspace';
import { useTrainingPreparation } from '../hooks/useTrainingPreparation';
import { TRAINING_AGENTS } from '../trainingAgents';

export function TrainingDataPage() {
  const { agentId } = useParams({ strict: false }) as { agentId?: string };
  const navigate = useNavigate();
  const activeAgent = TRAINING_AGENTS.find((agent) => agent.id === agentId) ?? TRAINING_AGENTS[0];
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const preparation = useTrainingPreparation(activeAgent.id);

  function selectAgent(id: string) {
    void navigate({
      to: '/admin/training-data/$agentId',
      params: { agentId: id },
    });
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const nextIndex =
      event.key === 'ArrowRight'
        ? (index + 1) % TRAINING_AGENTS.length
        : event.key === 'ArrowLeft'
          ? (index + TRAINING_AGENTS.length - 1) % TRAINING_AGENTS.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? TRAINING_AGENTS.length - 1
              : null;
    if (nextIndex === null) return;
    event.preventDefault();
    tabRefs.current[nextIndex]?.focus();
    selectAgent(TRAINING_AGENTS[nextIndex].id);
  }

  return (
    <PageContainer as="section">
      <div
        role="tablist"
        aria-label="Specialist agents"
        className="grid grid-cols-4 border-b border-border"
      >
        {TRAINING_AGENTS.map((agent, index) => (
          <button
            key={agent.id}
            ref={(element) => {
              tabRefs.current[index] = element;
            }}
            type="button"
            role="tab"
            id={`training-tab-${agent.id}`}
            aria-label={agent.label}
            title={agent.label}
            aria-selected={activeAgent.id === agent.id}
            aria-controls={activeAgent.id === agent.id ? `training-panel-${agent.id}` : undefined}
            tabIndex={activeAgent.id === agent.id ? 0 : -1}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
            onClick={() => selectAgent(agent.id)}
            className={cn(
              '-mb-px min-h-10 min-w-0 cursor-pointer truncate border-b-2 px-2 py-2 text-sm font-semibold transition-colors duration-120 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring motion-reduce:transition-none sm:px-4',
              activeAgent.id === agent.id
                ? 'border-primary bg-primary-soft text-primary'
                : 'border-transparent text-text-muted hover:bg-surface-subtle hover:text-text',
            )}
          >
            {agent.shortLabel}
          </button>
        ))}
      </div>
      <TrainingDataWorkspace
        key={activeAgent.id}
        agentId={activeAgent.id}
        credentials={preparation.credentials}
        onPrepare={preparation.prepareRun}
        isPreparing={preparation.isPreparing}
        preparationError={preparation.error}
        onHandoffSaved={preparation.acknowledgeHandoff}
      />
    </PageContainer>
  );
}
