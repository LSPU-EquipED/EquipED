import { useParams } from '@tanstack/react-router';
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
  const activeAgent = agentId ?? 'coordinator';
  const activeAgentMeta = AGENTS.find((a) => a.id === activeAgent) ?? AGENTS[0];

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-8">
      <h1 className="text-xl font-semibold">{activeAgentMeta.label} — Training Data</h1>
      <TrainingJobsPanel agentId={activeAgent} />
      <h2 className="text-lg font-semibold">Trained Adapters</h2>
      <AdapterListTable agentId={activeAgent} />
    </section>
  );
}
