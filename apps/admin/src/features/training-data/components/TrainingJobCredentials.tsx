import { useEffect, useId, useState } from 'react';
import { Check, Copy } from '@phosphor-icons/react';
import { Button, Input, TYPOGRAPHY, cn } from '@equiped/ui';
import { useCredentialCopy } from '../hooks/useCredentialCopy';
import { formatCountdown } from '../utils/trainingData.utils';
import type { TrainingJobCreateResponse } from '../types';

interface CredentialFieldProps {
  label: string;
  url: string;
  expiresAt: string;
  now: number;
}

function CredentialField({ label, url, expiresAt, now }: CredentialFieldProps) {
  const id = useId();
  const { copyState, copy } = useCredentialCopy(url);
  const expired = new Date(expiresAt).getTime() <= now;

  return (
    <div className="min-w-0 space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium text-text">
          {label}
        </label>
        <span
          id={`${id}-expiry`}
          className={cn('text-sm tabular-nums', expired ? 'text-destructive' : 'text-text-muted')}
        >
          {formatCountdown(expiresAt, now)}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <Input
            id={id}
            value={url}
            readOnly
            aria-describedby={`${id}-expiry`}
            onFocus={(event) => event.currentTarget.select()}
            className="min-w-0 font-mono text-[13px]"
          />
        </div>
        <Button
          type="button"
          variant="secondary"
          className="shrink-0"
          aria-label={`Copy ${label}`}
          disabled={expired || copyState === 'copying'}
          onClick={() => void copy()}
        >
          {copyState === 'copied' ? (
            <Check className="size-4" aria-hidden="true" />
          ) : (
            <Copy className="size-4" aria-hidden="true" />
          )}
          {copyState === 'copied' ? 'Copied' : 'Copy'}
        </Button>
      </div>
      {copyState === 'copied' && (
        <span role="status" className="sr-only">
          {label} copied.
        </span>
      )}
      {copyState === 'error' && (
        <p role="alert" className="text-sm text-destructive">
          Could not copy. Select the URL and copy it manually.
        </p>
      )}
    </div>
  );
}

export interface TrainingJobCredentialsProps {
  credentials: TrainingJobCreateResponse;
  onSaved: () => void;
}

export function TrainingJobCredentials({ credentials, onSaved }: TrainingJobCredentialsProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section
      aria-labelledby="notebook-handoff-title"
      className="space-y-5 rounded-md border border-border bg-surface p-4 sm:p-5"
    >
      <div className="space-y-1.5">
        <h2 id="notebook-handoff-title" className={TYPOGRAPHY.headingSm}>
          Continue in your notebook
        </h2>
        <p className="text-sm leading-relaxed text-text-muted">
          Download URL: first cell. Upload URL: final cell.
        </p>
        <p className="text-sm font-medium text-text">
          Save these single-use URLs before leaving or reloading; they cannot be retrieved again.
        </p>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <CredentialField
          label="Download URL"
          url={credentials.download_url}
          expiresAt={credentials.download_expires_at}
          now={now}
        />
        <CredentialField
          label="Upload URL"
          url={credentials.upload_url}
          expiresAt={credentials.upload_expires_at}
          now={now}
        />
      </div>
      <div className="flex justify-end border-t border-border pt-4">
        <Button variant="secondary" onClick={onSaved}>
          I've saved both URLs
        </Button>
      </div>
    </section>
  );
}
