import { useState } from 'react';
import { Button, Input, TYPOGRAPHY } from '@equiped/ui';
import { useCreateHostKey, useHostSync, useRevokeHostKey } from '../hooks/useHostSync';

function checkedText(lastSeen?: string | null): string {
  if (!lastSeen) return 'The host has not checked in yet.';
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(lastSeen).getTime()) / 60_000));
  if (minutes < 1) return 'Host last checked just now.';
  if (minutes < 60) return `Host last checked ${minutes} min ago.`;
  return `Host last checked ${Math.floor(minutes / 60)} h ago.`;
}

export function HostSyncPanel() {
  const { data, isLoading, isError } = useHostSync();
  const create = useCreateHostKey();
  const revoke = useRevokeHostKey();
  const [newKey, setNewKey] = useState<string | null>(null);

  function onCreate() {
    if (create.isPending) return;
    create.mutate(undefined, { onSuccess: (created) => setNewKey(created.key) });
  }

  return (
    <section aria-labelledby="host-sync-title" className="min-w-0 space-y-3">
      <h2 id="host-sync-title" className={TYPOGRAPHY.headingSm}>
        Host sync
      </h2>
      <p className="max-w-3xl text-[13px] leading-5 text-text-muted">
        A small script on the model server&apos;s computer uses this key to download new fine-tuned
        models. It cannot publish, delete or change anything.
      </p>
      {isLoading ? (
        <p className="text-sm text-text-muted">Checking host sync…</p>
      ) : isError || !data ? (
        <p role="alert" className="text-sm text-destructive">
          Could not load host sync status.
        </p>
      ) : (
        <div className="space-y-3 rounded-md border border-border bg-surface p-4">
          <p className="text-sm text-text">
            {data.has_active_key ? checkedText(data.last_seen_at) : 'No key yet.'}
          </p>
          {newKey ? (
            <div className="space-y-1.5">
              <label htmlFor="host-key" className="block text-[13px] font-medium text-text">
                Host key
              </label>
              <Input
                id="host-key"
                value={newKey}
                readOnly
                className="font-mono text-sm"
                onFocus={(event) => event.currentTarget.select()}
              />
              <p className="text-xs text-text-muted">
                Shown once. Copy it into the script&apos;s settings now.
              </p>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={create.isPending}
              onClick={onCreate}
            >
              {data.has_active_key ? 'Replace host key' : 'Create host key'}
            </Button>
            {data.has_active_key ? (
              <Button
                type="button"
                variant="secondary"
                disabled={revoke.isPending}
                onClick={() => {
                  revoke.mutate(undefined, { onSuccess: () => setNewKey(null) });
                }}
              >
                Revoke key
              </Button>
            ) : null}
          </div>
          {create.isError || revoke.isError ? (
            <p role="alert" className="text-sm text-destructive">
              That did not work. Try again.
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}
