import { useState } from 'react';
import { useStartTrainingJob } from './useStartTrainingJob';
import type { TrainingJobCreateResponse } from '../types';

// Called by the page, outside the keyed workspace, to retain each specialist's handoff.
export function useTrainingPreparation(agentId: string) {
  const [handoffs, setHandoffs] = useState<Record<string, TrainingJobCreateResponse | undefined>>(
    {},
  );
  const prepare = useStartTrainingJob((credentials) => {
    setHandoffs((current) => ({ ...current, [credentials.agent_id]: credentials }));
  });

  return {
    credentials: handoffs[agentId],
    prepareRun: () => prepare.mutate(agentId),
    isPreparing: prepare.isPending,
    error:
      prepare.isError && prepare.variables === agentId
        ? prepare.error instanceof Error
          ? prepare.error.message
          : 'Could not start the training run. Try again.'
        : null,
    acknowledgeHandoff: () => setHandoffs((current) => ({ ...current, [agentId]: undefined })),
  };
}
