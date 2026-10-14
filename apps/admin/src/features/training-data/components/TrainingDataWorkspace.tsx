import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowClockwise } from '@phosphor-icons/react';
import { Button } from '@equiped/ui';
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
  const client = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function refresh() {
    setIsRefreshing(true);
    try {
      await Promise.all(
        [
          ['trainingJobs', agentId],
          ['trainedAdapters', agentId],
          ['datasetReadiness', agentId],
          ['hostSync'],
        ].map((queryKey) => client.refetchQueries({ queryKey, exact: true, type: 'active' }))
      );
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <div
      role="tabpanel"
      id={`training-panel-${agentId}`}
      aria-labelledby={`training-tab-${agentId}`}
      tabIndex={0}
      className="min-w-0 space-y-8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl space-y-1 text-sm leading-6 text-text-muted">
          <p>
            A fine-tuned model is the base AI after it has learned from reviewer corrections. Start
            a training run, finish it in Colab, then choose which fine-tuned model to use.
          </p>
          <p>Refresh to check for new models and updated run status.</p>
        </div>
        <Button
          variant="secondary"
          aria-label="Refresh training data"
          aria-busy={isRefreshing}
          disabled={isRefreshing}
          onClick={() => void refresh()}
        >
          <ArrowClockwise className="size-4" aria-hidden="true" />
          {isRefreshing ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>
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
