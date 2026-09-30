import { AdapterListTable } from './AdapterListTable';
import { DatasetReadinessCard } from './DatasetReadinessCard';
import { TrainingJobsPanel } from './TrainingJobsPanel';
import { TrainingJobCredentials } from './TrainingJobCredentials';
import type { TrainingJobCreateResponse } from '../types';

interface TrainingDataWorkspaceProps {
  agentId: string;
  credentials?: TrainingJobCreateResponse;
  onPrepare: () => void;
  isPreparing: boolean;
  preparationError: string | null;
  onHandoffSaved: () => void;
}

export function TrainingDataWorkspace({
  agentId,
  credentials,
  onPrepare,
  isPreparing,
  preparationError,
  onHandoffSaved,
}: TrainingDataWorkspaceProps) {
  return (
    <div
      role="tabpanel"
      id={`training-panel-${agentId}`}
      aria-labelledby={`training-tab-${agentId}`}
      tabIndex={0}
      className="min-w-0 space-y-8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <DatasetReadinessCard
        agentId={agentId}
        onPrepare={onPrepare}
        isPreparing={isPreparing}
        hasHandoff={Boolean(credentials)}
        preparationError={preparationError}
      />
      {credentials && (
        <TrainingJobCredentials
          key={credentials.job_id}
          credentials={credentials}
          onSaved={onHandoffSaved}
        />
      )}
      <TrainingJobsPanel agentId={agentId} />
      <AdapterListTable agentId={agentId} />
    </div>
  );
}
