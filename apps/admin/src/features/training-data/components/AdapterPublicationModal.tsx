import { ConfirmationModal } from '@equiped/ui';
import type { AdapterPublicationAction } from '../hooks/useAdapterPublication';

interface AdapterPublicationModalProps {
  agentId: string;
  action: AdapterPublicationAction | null;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  isPending: boolean;
}

export function AdapterPublicationModal({
  agentId,
  action,
  onClose,
  onConfirm,
  isPending,
}: AdapterPublicationModalProps) {
  const agentLabel = agentId.toUpperCase();
  return (
    <ConfirmationModal
      isOpen={action !== null}
      onClose={onClose}
      onConfirm={onConfirm}
      variant="primary"
      title={
        action?.kind === 'unpublish'
          ? `Unpublish ${agentLabel} v${action.adapter.version}?`
          : `Publish ${agentLabel} v${action?.adapter.version ?? ''}?`
      }
      description={
        action?.kind === 'unpublish'
          ? `Faculty evaluations will stop using ${agentLabel} v${action.adapter.version}.`
          : `Faculty evaluations will use ${agentLabel} v${action?.adapter.version ?? ''} from now on.`
      }
      confirmLabel={
        action?.kind === 'unpublish'
          ? `Unpublish v${action.adapter.version}`
          : `Publish v${action?.adapter.version ?? ''}`
      }
      isPending={isPending}
    />
  );
}
