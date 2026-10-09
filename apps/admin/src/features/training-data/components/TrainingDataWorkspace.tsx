import { AdapterListTable } from './AdapterListTable';
import { HostSyncPanel } from './HostSyncPanel';
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
      <p className="max-w-3xl text-sm leading-6 text-text-muted">
        A fine-tuned model is the base AI after it has learned from reviewer corrections. Start a
        training run, finish it in Colab, then choose which fine-tuned model to use.
      </p>
      <div className="space-y-4">
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
      </div>
      <TrainingJobsPanel agentId={agentId} />
      <AdapterListTable agentId={agentId} />
      <HostSyncPanel />
    </div>
  );
}
