import { Copy } from '@phosphor-icons/react';
import { Button } from '@equiped/ui';
import { useHostSync } from '../hooks/useHostSync';

export function AdapterLoadHint({ filename }: { filename: string }) {
  const { data } = useHostSync();
  if (data?.has_active_key) {
    return (
      <p className="max-w-3xl text-[13px] leading-5 text-text-muted">
        The host sync script downloads this file by itself. Restart the model server when it is idle
        to load it.
      </p>
    );
  }
  const flag = `--lora-scaled ${filename}:0.0`;
  return (
    <div className="space-y-2 text-[13px] leading-5 text-text-muted">
      <p className="max-w-3xl [overflow-wrap:anywhere]">
        {`Download the file from this page and save it as ${filename} in the models folder. Add this to start-gemma.bat with the file's full path (for example F:\\Dev\\Models\\gemma\\adapters\\${filename}), then restart the model server.`}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <code className="min-w-0 rounded-sm bg-surface-subtle px-3 py-2 font-mono text-xs [overflow-wrap:anywhere]">
          {flag}
        </code>
        <Button
          type="button"
          variant="secondary"
          onClick={() => void Promise.resolve(navigator.clipboard?.writeText(flag)).catch(() => {})}
        >
          <Copy className="size-3.5" aria-hidden="true" />
          Copy
        </Button>
      </div>
    </div>
  );
}
