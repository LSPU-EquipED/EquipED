import { Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import { TYPOGRAPHY, TABLE_STYLES, TableSkeleton, cn } from '@equiped/ui';
import { useAdapterPublication } from '../hooks/useAdapterPublication';
import { getPublishedAdapterWarning } from '../utils/adapterPublication.utils';
import { useTrainedAdapters } from '../hooks/useTrainedAdapters';
import { AdapterRow } from './AdapterRow';
import { AdapterPublicationModal } from './AdapterPublicationModal';

export function AdapterListTable({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useTrainedAdapters(agentId);
  const publication = useAdapterPublication(agentId);
  const adapters = data?.adapters ?? [];
  const bannerMessage = getPublishedAdapterWarning(data);

  return (
    <section aria-labelledby="uploaded-adapters-title" className="space-y-3">
      <div className="flex items-baseline gap-3">
        <h2 id="uploaded-adapters-title" className={TYPOGRAPHY.headingSm}>
          Uploaded adapters
        </h2>
        {!isLoading && !isError && (
          <span className="text-sm tabular-nums text-text-muted">
            {adapters.length} {adapters.length === 1 ? 'adapter' : 'adapters'}
          </span>
        )}
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
            { label: 'Actions', skeletonClassName: 'h-8 w-20' },
            { label: 'Details', skeletonClassName: 'h-4 w-8' },
          ]}
        />
      ) : isError ? (
        <p role="alert" className="border-y border-border py-5 text-sm text-destructive">
          Failed to load trained adapters.
        </p>
      ) : adapters.length === 0 ? (
        <p className="border-y border-border py-5 text-sm text-text-muted">
          No adapters uploaded yet.
        </p>
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
          <div className={TABLE_STYLES.wrapper}>
            <table className={TABLE_STYLES.table} aria-label="Uploaded adapters">
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th className={cn(TABLE_STYLES.th, 'w-20')}>Version</th>
                  <th className={TABLE_STYLES.th}>Status</th>
                  <th className={TABLE_STYLES.th}>Uploaded</th>
                  <th className={TABLE_STYLES.th}>Size</th>
                  <th className={TABLE_STYLES.th}>Actions</th>
                  <th className="w-14">
                    <span className="sr-only">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {adapters.map((adapter) => (
                  <AdapterRow
                    key={adapter.adapter_id}
                    adapter={adapter}
                    onPublish={() => publication.requestAction({ kind: 'publish', adapter })}
                    onUnpublish={() => publication.requestAction({ kind: 'unpublish', adapter })}
                  />
                ))}
              </tbody>
            </table>
          </div>
          {publication.error ? (
            <div
              role="alert"
              className="flex items-center gap-2.5 border-t border-border bg-destructive-soft px-5 py-3 text-sm font-semibold text-destructive"
            >
              <Warning className="size-4 shrink-0" aria-hidden="true" />
              <span>{getErrorMessage(publication.error)}</span>
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

      <AdapterPublicationModal
        agentId={agentId}
        action={publication.pendingAction}
        onClose={publication.closeConfirmation}
        onConfirm={publication.confirmAction}
        isPending={publication.isPending}
      />
    </section>
  );
}
