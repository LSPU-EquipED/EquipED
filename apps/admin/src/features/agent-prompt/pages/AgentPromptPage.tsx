import { useRef, type KeyboardEvent } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { cn, PageContainer } from '@equiped/ui';
import { AgentPromptWorkspace } from '../components/AgentPromptWorkspace';

const AGENTS = [
  { id: 'coordinator', label: 'Program Coordinator', shortLabel: 'Coordinator' },
  { id: 'sme', label: 'Subject Matter Expert', shortLabel: 'SME' },
  { id: 'gad', label: 'Gender & Development (GAD)', shortLabel: 'GAD' },
  { id: 'itso', label: 'Innovation and Technology Support Office', shortLabel: 'ITSO' },
] as const;

export function AgentPromptPage() {
  const { agentId } = useParams({ strict: false }) as { agentId?: string };
  const navigate = useNavigate();
  const activeAgent = AGENTS.find((agent) => agent.id === agentId) ?? AGENTS[0];
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const nextIndex =
      event.key === 'ArrowRight'
        ? (index + 1) % AGENTS.length
        : event.key === 'ArrowLeft'
          ? (index + AGENTS.length - 1) % AGENTS.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? AGENTS.length - 1
              : null;
    if (nextIndex === null) return;
    event.preventDefault();
    tabRefs.current[nextIndex]?.focus();
    void navigate({ to: '/admin/prompts/$agentId', params: { agentId: AGENTS[nextIndex].id } });
  }

  return (
    <PageContainer as="section">
      <section className="space-y-5">
        <div
          role="tablist"
          aria-label="Specialist agents"
          className="grid grid-cols-4 border-b border-border"
        >
          {AGENTS.map((agent, index) => (
            <button
              key={agent.id}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              type="button"
              role="tab"
              id={`prompt-tab-${agent.id}`}
              aria-label={agent.label}
              title={agent.label}
              aria-selected={activeAgent.id === agent.id}
              aria-controls={activeAgent.id === agent.id ? `prompt-panel-${agent.id}` : undefined}
              tabIndex={activeAgent.id === agent.id ? 0 : -1}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
              onClick={() =>
                void navigate({ to: '/admin/prompts/$agentId', params: { agentId: agent.id } })
              }
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
        <AgentPromptWorkspace
          key={activeAgent.id}
          agentId={activeAgent.id}
          agentLabel={activeAgent.label}
        />
      </section>
    </PageContainer>
  );
}
