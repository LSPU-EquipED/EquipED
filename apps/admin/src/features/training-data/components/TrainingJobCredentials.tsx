import { useEffect, useState } from 'react';
import { Check, Clock, Copy } from '@phosphor-icons/react';
import { cn } from '@equiped/ui';
import { formatCountdown } from '../utils/trainingData.utils';
import type { TrainingJobCreateResponse } from '../types';

interface CredentialFieldProps {
  label: string;
  url: string;
  expiresAt: string;
  now: number;
}

function CredentialField({ label, url, expiresAt, now }: CredentialFieldProps) {
  const [copied, setCopied] = useState(false);
  const expired = new Date(expiresAt).getTime() <= now;

  const handleCopy = () => {
    void navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-text">{label}</span>
        <span
          className={cn(
            'inline-flex items-center gap-1 text-[11px] font-semibold tabular-nums',
            expired ? 'text-destructive' : 'text-text-muted',
          )}
        >
          <Clock className="size-3" aria-hidden="true" />
          {formatCountdown(expiresAt, now)}
        </span>
      </div>
      <div className="flex items-stretch gap-2">
        <code className="min-w-0 flex-1 truncate rounded-sm border border-input bg-surface px-3 py-2 font-mono text-xs text-text">
          {url}
        </code>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-semibold text-primary transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {copied ? (
            <>
              <Check className="size-3.5 text-success" aria-hidden="true" />
              <span className="text-success">Copied</span>
            </>
          ) : (
            <>
              <Copy className="size-3.5" aria-hidden="true" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export interface TrainingJobCredentialsProps {
  credentials: TrainingJobCreateResponse;
}

export function TrainingJobCredentials({ credentials }: TrainingJobCredentialsProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4 border-b border-border bg-surface-subtle p-4 sm:p-5">
      <p className="text-xs font-semibold text-text-muted">
        Paste these into your Colab notebook now — each is shown only once.
      </p>
      <CredentialField
        label="Download URL (notebook cell 1)"
        url={credentials.download_url}
        expiresAt={credentials.download_expires_at}
        now={now}
      />
      <CredentialField
        label="Upload URL (notebook final cell)"
        url={credentials.upload_url}
        expiresAt={credentials.upload_expires_at}
        now={now}
      />
    </div>
  );
}
