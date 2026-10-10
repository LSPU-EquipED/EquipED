import { useId } from 'react';
import { Check, Copy } from '@phosphor-icons/react';
import { Button, Input, cn } from '@equiped/ui';
import { useCredentialCopy } from '../hooks/useCredentialCopy';
import { formatCountdown } from '../utils/trainingData.utils';

interface TrainingCredentialFieldProps {
  label: string;
  hint: string;
  url: string;
  expiresAt: string;
  now: number;
}

export function TrainingCredentialField({
  label,
  hint,
  url,
  expiresAt,
  now,
}: TrainingCredentialFieldProps) {
  const id = useId();
  const { copyState, copy } = useCredentialCopy(url);
  const expired = new Date(expiresAt).getTime() <= now;

  return (
    <div className="grid min-w-0 gap-3 p-4 sm:p-5 lg:grid-cols-[10rem_minmax(0,1fr)] lg:gap-5">
      <div className="space-y-1">
        <label htmlFor={id} className="block text-[13px] font-medium leading-5 text-text">
          {label}
        </label>
        <p id={`${id}-hint`} className="text-xs leading-4 text-text-muted">
          {hint}
        </p>
      </div>
      <div className="min-w-0 space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <Input
              id={id}
              value={url}
              readOnly
              aria-describedby={`${id}-hint ${id}-expiry`}
              onFocus={(event) => event.currentTarget.select()}
              className="min-w-0 font-mono text-sm"
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
        <p
          id={`${id}-expiry`}
          className={cn(
            'text-xs leading-4 tabular-nums',
            expired ? 'text-destructive' : 'text-text-muted',
          )}
        >
          {formatCountdown(expiresAt, now)}
        </p>
        {copyState === 'copied' && (
          <span role="status" className="sr-only">
            {label} copied.
          </span>
        )}
        {copyState === 'error' && (
          <p role="alert" className="text-[13px] leading-5 text-destructive">
            Could not copy. Select the link and copy it manually.
          </p>
        )}
      </div>
    </div>
  );
}
