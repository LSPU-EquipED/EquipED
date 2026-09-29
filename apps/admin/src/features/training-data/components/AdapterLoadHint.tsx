import { Copy } from '@phosphor-icons/react';

export function AdapterLoadHint({ filename }: { filename: string }) {
  const flag = `--lora-scaled ${filename}:0.0`;
  return (
    <div className="mt-1 space-y-1 text-xs font-normal text-text-muted">
      <p>Ask the host owner to add this to start-gemma.bat, then restart the server:</p>
      <div className="flex items-center gap-2">
        <code className="rounded-sm bg-surface-subtle px-2 py-1 font-mono">{flag}</code>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-sm border border-border px-2 py-1 font-semibold text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => void navigator.clipboard.writeText(flag)}
        >
          <Copy className="size-3.5" aria-hidden="true" />
          Copy
        </button>
      </div>
    </div>
  );
}
