import { Copy } from '@phosphor-icons/react';
import { Button } from '@equiped/ui';

export function AdapterLoadHint({ filename }: { filename: string }) {
  const flag = `--lora-scaled ${filename}:0.0`;
  return (
    <div className="space-y-2 text-[13px] leading-5 text-text-muted">
      <p className="max-w-3xl [overflow-wrap:anywhere]">
        {`Save the file as ${filename} and add this to start-gemma.bat with the file's full path (for example F:\\Dev\\Models\\gemma\\adapters\\${filename}), then restart the server.`}
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
