import { useState } from 'react';
import { usePublishAdapter, useUnpublishAdapter } from './usePublishAdapter';
import type { TrainedAdapterItem } from '../types';

export interface AdapterPublicationAction {
  kind: 'publish' | 'unpublish';
  adapter: TrainedAdapterItem;
}

export function useAdapterPublication(agentId: string) {
  const publish = usePublishAdapter(agentId);
  const unpublish = useUnpublishAdapter(agentId);
  const [pendingAction, setPendingAction] = useState<AdapterPublicationAction | null>(null);

  function requestAction(action: AdapterPublicationAction) {
    publish.reset();
    unpublish.reset();
    setPendingAction(action);
  }

  async function confirmAction() {
    if (!pendingAction) return;
    try {
      if (pendingAction.kind === 'publish') {
        await publish.mutateAsync(pendingAction.adapter.adapter_id);
      } else {
        await unpublish.mutateAsync();
      }
    } catch {
      // Keep the existing flow: close the dialog and report the mutation error in the table.
    }
    setPendingAction(null);
  }

  return {
    pendingAction,
    requestAction,
    confirmAction,
    closeConfirmation: () => setPendingAction(null),
    isPending: publish.isPending || unpublish.isPending,
    error: publish.error ?? unpublish.error,
  };
}
