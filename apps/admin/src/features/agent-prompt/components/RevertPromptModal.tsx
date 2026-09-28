import { ConfirmationModal } from '@equiped/ui';

type RevertPromptModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void> | void;
  agentLabel: string;
  versionNumber: number;
  isPending?: boolean;
  error?: string | null;
};

export function RevertPromptModal({
  isOpen,
  onClose,
  onConfirm,
  agentLabel,
  versionNumber,
  isPending,
  error,
}: RevertPromptModalProps) {
  return (
    <ConfirmationModal
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title={`Restore version ${versionNumber}?`}
      description={
        <p>
          This publishes a new active version of the {agentLabel} prompt using the text from version{' '}
          {versionNumber}. Future evaluations will use it. Previous versions remain in history.
        </p>
      }
      confirmLabel="Restore version"
      variant="primary"
      isPending={isPending}
      error={error}
    />
  );
}
