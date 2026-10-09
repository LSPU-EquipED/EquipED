import { Button, TYPOGRAPHY } from '@equiped/ui';
import { useCredentialClock } from '../hooks/useCredentialClock';
import type { TrainingJobCreateResponse } from '../types';
import { TrainingCredentialField } from './TrainingCredentialField';

export interface TrainingJobCredentialsProps {
  credentials: TrainingJobCreateResponse;
  onSaved: () => void;
}

export function TrainingJobCredentials({ credentials, onSaved }: TrainingJobCredentialsProps) {
  const now = useCredentialClock();

  return (
    <section
      aria-labelledby="notebook-handoff-title"
      className="overflow-hidden rounded-md border border-border bg-surface"
    >
      <div className="space-y-1.5 border-b border-border px-4 py-4 sm:px-5">
        <h2 id="notebook-handoff-title" className={TYPOGRAPHY.headingSm}>
          Continue in Colab
        </h2>
        <p className="max-w-3xl text-[13px] leading-5 text-text-muted">
          Save these two single-use links before leaving or reloading; they cannot be shown again.
        </p>
      </div>
      <div className="divide-y divide-border">
        <TrainingCredentialField
          label="Step 1 link"
          hint="Gets the data. Paste into the first Colab cell."
          url={credentials.download_url}
          expiresAt={credentials.download_expires_at}
          now={now}
        />
        <TrainingCredentialField
          label="Step 2 link"
          hint="Sends back the result. Paste into the final Colab cell."
          url={credentials.upload_url}
          expiresAt={credentials.upload_expires_at}
          now={now}
        />
      </div>
      <div className="flex justify-end border-t border-border px-4 py-3 sm:px-5">
        <Button variant="secondary" className="w-full sm:w-auto" onClick={onSaved}>
          I've saved both links
        </Button>
      </div>
    </section>
  );
}
