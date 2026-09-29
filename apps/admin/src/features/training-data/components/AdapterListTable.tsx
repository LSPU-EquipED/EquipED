import { useState } from 'react';
import { Package, Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import {
  Button,
  CARD_STYLES,
  ConfirmationModal,
  TABLE_STYLES,
  TableSkeleton,
  cn,
} from '@equiped/ui';
import { usePublishAdapter, useUnpublishAdapter } from '../hooks/usePublishAdapter';
import { useTrainedAdapters } from '../hooks/useTrainedAdapters';
import type { TrainedAdapterItem } from '../types';
import { formatSize } from '../utils/trainingData.utils';
import { AdapterLoadHint } from './AdapterLoadHint';

type PendingAction = {
  kind: 'publish' | 'unpublish';
  adapter: TrainedAdapterItem;
};

function loadLabel(loaded: boolean | null) {
  if (loaded === true) return 'Loaded';
  if (loaded === false) return 'Not loaded';
  return 'Unknown';
}

const BADGE = 'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold';

export function AdapterListTable({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useTrainedAdapters(agentId);
  const publish = usePublishAdapter(agentId);
  const unpublish = useUnpublishAdapter(agentId);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const adapters = data?.adapters ?? [];
  const agentLabel = agentId.toUpperCase();

  const publishedAdapter = adapters.find((a) => a.published) ?? null;
  const bannerMessage = !publishedAdapter
    ? null
    : data?.server_reachable === false
      ? `The model server could not be reached, so it is unknown whether published adapter v${publishedAdapter.version} is loaded.`
      : publishedAdapter.loaded === false
        ? `Published adapter v${publishedAdapter.version} is not loaded on the model server. Add its load flag below and restart the server.`
        : null;
  const mutationError = publish.error ?? unpublish.error;

  function openConfirm(action: PendingAction) {
    publish.reset();
    unpublish.reset();
    setPending(action);
  }

  async function handleConfirm() {
    if (!pending) return;
    try {
      if (pending.kind === 'publish') {
        await publish.mutateAsync(pending.adapter.adapter_id);
      } else {
        await unpublish.mutateAsync();
      }
    } catch {
      // The error is shown beneath the table via the mutation state.
    }
    setPending(null);
  }

  return (
    <div className={CARD_STYLES.ledger}>
      <div className={CARD_STYLES.header}>
        <div className="flex items-center gap-2">
          <Package className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-text">Trained Adapters</h2>
        </div>
      </div>

      {isLoading ? (
        <TableSkeleton
          ariaLabel="Loading trained adapters"
          columns={[
            {
              label: 'Version',
              headerClassName: 'w-20',
              skeletonClassName: 'h-4 w-8',
            },
            { label: 'Status', skeletonClassName: 'h-5 w-24' },
            { label: 'Uploaded', skeletonClassName: 'h-4 w-32' },
            { label: 'Size', skeletonClassName: 'h-4 w-16' },
            { label: 'Hash', skeletonClassName: 'h-4 w-24' },
            { label: 'Source Job', skeletonClassName: 'h-4 w-40' },
            { label: 'Actions', skeletonClassName: 'h-8 w-20' },
          ]}
        />
      ) : isError ? (
        <div className="flex items-center justify-center gap-2.5 bg-destructive-soft px-4 py-12 text-sm font-semibold text-destructive">
          <Warning className="size-5 shrink-0" aria-hidden="true" />
          <span>Failed to load trained adapters.</span>
        </div>
      ) : adapters.length === 0 ? (
        <div className="space-y-1.5 py-16 text-center text-text-muted">
          <Package className="mx-auto size-8 text-text-muted/40" aria-hidden="true" />
          <p className="text-sm font-semibold text-text">No trained adapters uploaded yet.</p>
          <p className="mx-auto max-w-sm text-xs text-text-muted">
            Once a Colab training run pushes an adapter back, it will appear here with a link to the
            dataset snapshot that trained it.
          </p>
        </div>
      ) : (
        <>
          {bannerMessage ? (
            <div
              role="alert"
              className="flex items-center gap-2.5 border-b border-border bg-destructive-soft px-5 py-3 text-sm font-semibold text-destructive"
            >
              <Warning className="size-4 shrink-0" aria-hidden="true" />
              <span>{bannerMessage}</span>
            </div>
          ) : null}
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th className={cn(TABLE_STYLES.th, 'w-20')}>Version</th>
                  <th className={TABLE_STYLES.th}>Status</th>
                  <th className={TABLE_STYLES.th}>Uploaded</th>
                  <th className={TABLE_STYLES.th}>Size</th>
                  <th className={TABLE_STYLES.th}>Hash</th>
                  <th className={TABLE_STYLES.th}>Source Job</th>
                  <th className={TABLE_STYLES.th}>Actions</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {adapters.map((adapter: TrainedAdapterItem) => (
                  <tr key={adapter.adapter_id} className={TABLE_STYLES.tr}>
                    <td className={cn(TABLE_STYLES.tdData, 'font-semibold')}>v{adapter.version}</td>
                    <td className={TABLE_STYLES.tdData}>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {adapter.published ? (
                          <span
                            className={cn(BADGE, 'border-primary/30 bg-primary-soft text-primary')}
                          >
                            Published
                          </span>
                        ) : null}
                        <span
                          className={cn(BADGE, 'border-border bg-surface-subtle text-text-muted')}
                        >
                          {loadLabel(adapter.loaded)}
                        </span>
                      </div>
                      {adapter.loaded === false ? (
                        <AdapterLoadHint filename={adapter.gguf_filename} />
                      ) : null}
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-text-muted')}>
                      {new Date(adapter.created_at).toLocaleString()}
                    </td>
                    <td className={TABLE_STYLES.tdData}>{formatSize(adapter.size_bytes)}</td>
                    <td
                      className={cn(TABLE_STYLES.tdData, 'font-mono text-xs text-text-muted')}
                      title={adapter.file_sha256}
                    >
                      {adapter.file_sha256.slice(0, 12)}…
                    </td>
                    <td
                      className={cn(TABLE_STYLES.tdData, 'font-mono text-xs text-text-muted')}
                      title={adapter.job_id}
                    >
                      <span className="inline-block max-w-[12rem] truncate align-middle">
                        {adapter.job_id}
                      </span>
                    </td>
                    <td className={TABLE_STYLES.tdData}>
                      {adapter.published ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => openConfirm({ kind: 'unpublish', adapter })}
                        >
                          Unpublish
                        </Button>
                      ) : (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={adapter.loaded !== true}
                          onClick={() => openConfirm({ kind: 'publish', adapter })}
                        >
                          Publish
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {mutationError ? (
            <div
              role="alert"
              className="flex items-center gap-2.5 border-t border-border bg-destructive-soft px-5 py-3 text-sm font-semibold text-destructive"
            >
              <Warning className="size-4 shrink-0" aria-hidden="true" />
              <span>{getErrorMessage(mutationError)}</span>
            </div>
          ) : null}
          {data && data.unrecognized_server_adapters.length > 0 ? (
            <div className="border-t border-border px-5 py-3 text-xs text-text-muted">
              <p className="font-semibold text-text">Unrecognized files on the server</p>
              <ul className="mt-1 list-disc pl-5 font-mono">
                {data.unrecognized_server_adapters.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}

      <ConfirmationModal
        isOpen={pending !== null}
        onClose={() => setPending(null)}
        onConfirm={handleConfirm}
        variant="primary"
        title={
          pending?.kind === 'unpublish'
            ? `Unpublish ${agentLabel} v${pending.adapter.version}?`
            : `Publish ${agentLabel} v${pending?.adapter.version ?? ''}?`
        }
        description={
          pending?.kind === 'unpublish'
            ? `Faculty evaluations will stop using ${agentLabel} v${pending.adapter.version}.`
            : `Faculty evaluations will use ${agentLabel} v${pending?.adapter.version ?? ''} from now on.`
        }
        confirmLabel={
          pending?.kind === 'unpublish'
            ? `Unpublish v${pending.adapter.version}`
            : `Publish v${pending?.adapter.version ?? ''}`
        }
        isPending={publish.isPending || unpublish.isPending}
      />
    </div>
  );
}
