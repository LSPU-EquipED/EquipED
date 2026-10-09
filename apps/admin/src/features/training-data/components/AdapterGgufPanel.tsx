import { useRef, useState } from 'react';
import { Button } from '@equiped/ui';
import type { TrainedAdapterItem } from '../types';
import { useGgufDownloadLink, useRemoveGguf, useUploadGguf } from '../hooks/useAdapterGguf';
import { navigateTo } from '../utils/navigation';
import { formatSize } from '../utils/trainingData.utils';

const LINK_HOURS = 24;

function errorText(error: unknown): string {
  return error instanceof Error && error.message ? error.message : 'Something went wrong.';
}

function formatTime(iso: string): string | null {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleString();
}

export function AdapterGgufPanel({
  adapter,
  published,
  onChanged,
}: {
  adapter: Pick<TrainedAdapterItem, 'adapter_id' | 'agent_id' | 'gguf' | 'gguf_filename'>;
  published: boolean;
  onChanged?: () => void;
}) {
  const { agent_id: agentId, adapter_id: adapterId, gguf_filename: name } = adapter;
  const gguf = adapter.gguf ?? null;
  const fileInput = useRef<HTMLInputElement>(null);
  const [confirming, setConfirming] = useState(false);
  const [expiry, setExpiry] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const upload = useUploadGguf(agentId, adapterId);
  const remove = useRemoveGguf(agentId, adapterId);
  const link = useGgufDownloadLink(agentId, adapterId);

  const fail = (error: unknown) => setMessage(errorText(error));

  const onFile = (file: File | undefined) => {
    if (!file) return;
    setMessage(null);
    upload.mutate({ file, replace: gguf !== null }, { onSuccess: () => onChanged?.(), onError: fail });
    if (fileInput.current) fileInput.current.value = '';
  };

  const download = () => {
    setMessage(null);
    link.mutate(LINK_HOURS, { onSuccess: (r) => navigateTo(r.url), onError: fail });
  };

  const copyLink = () => {
    setMessage(null);
    setExpiry(null);
    link.mutate(LINK_HOURS, {
      onError: fail,
      onSuccess: async (r) => {
        try {
          await navigator.clipboard.writeText(r.url);
          const until = formatTime(r.expires_at);
          setExpiry(until ? `Link valid until ${until}` : 'Link copied');
        } catch {
          setMessage('Could not copy the link. Use Download instead.');
        }
      },
    });
  };

  const confirmRemove = () => {
    setConfirming(false);
    setMessage(null);
    remove.mutate(undefined, { onSuccess: () => onChanged?.(), onError: fail });
  };

  const uploadedAt = gguf ? formatTime(gguf.uploaded_at) : null;

  return (
    <section className="mt-3 space-y-2 border-t border-border pt-3" aria-label="GGUF file">
      <p className="text-[13px] font-medium leading-5 text-text">GGUF file</p>
      <input
        ref={fileInput}
        type="file"
        accept=".gguf"
        className="hidden"
        aria-label={`Choose GGUF file for ${name}`}
        onChange={(e) => onFile(e.target.files?.[0])}
      />
      {gguf ? (
        <div className="space-y-2 text-[13px] leading-5 text-text-muted">
          <p>
            <span>{formatSize(gguf.size_bytes)}</span>
            {uploadedAt ? <span>{` · uploaded ${uploadedAt}`}</span> : null}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <code className="min-w-0 rounded-sm bg-surface-subtle px-2 py-1 font-mono text-xs [overflow-wrap:anywhere]">
              {gguf.sha256}
            </code>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              aria-label={`Copy SHA-256 for ${name}`}
              onClick={() =>
                void Promise.resolve(navigator.clipboard?.writeText(gguf.sha256)).catch(() => {})
              }
            >
              Copy
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              aria-label={`Download ${name}`}
              disabled={link.isPending}
              onClick={download}
            >
              Download
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              aria-label={`Copy download link for ${name}`}
              disabled={link.isPending}
              onClick={copyLink}
            >
              Copy download link
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              aria-label={`Replace file ${name}`}
              disabled={upload.isPending}
              onClick={() => fileInput.current?.click()}
            >
              Replace
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              aria-label={`Remove file ${name}`}
              disabled={published || remove.isPending}
              title={
                published
                  ? 'The published fine-tuned model file cannot be removed. Unpublish it first.'
                  : undefined
              }
              onClick={() => setConfirming(true)}
            >
              Remove file
            </Button>
          </div>
          {confirming ? (
            <div
              className="flex flex-wrap items-center gap-2"
              role="group"
              aria-label="Confirm remove"
            >
              <span>Remove the stored file? Existing download links stop working.</span>
              <Button
                type="button"
                size="sm"
                aria-label={`Confirm remove ${name}`}
                onClick={confirmRemove}
              >
                Remove
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 text-[13px] text-text-muted">
          <span>Not uploaded</span>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            aria-label={`Upload GGUF ${name}`}
            disabled={upload.isPending}
            onClick={() => fileInput.current?.click()}
          >
            Upload GGUF
          </Button>
        </div>
      )}
      {upload.isPending ? (
        <p className="text-[13px] text-text-muted" role="status">
          Uploading...
        </p>
      ) : null}
      {expiry ? (
        <p className="text-[13px] text-text-muted" role="status">
          {expiry}
        </p>
      ) : null}
      {message ? (
        <p className="text-[13px] text-danger" role="alert">
          {message}
        </p>
      ) : null}
    </section>
  );
}
