import { Stack, Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import { TYPOGRAPHY, TABLE_STYLES, TableSkeleton, cn } from '@equiped/ui';
import type { TableSkeletonColumn } from '@equiped/ui';
import { useAdapterPublication } from '../hooks/useAdapterPublication';
import { getPublishedAdapterWarning } from '../utils/adapterPublication.utils';
import { useTrainedAdapters } from '../hooks/useTrainedAdapters';
import { useTrainingTablePagination } from '../hooks/useTrainingTablePagination';
import { AdapterRow } from './AdapterRow';
import { AdapterPublicationModal } from './AdapterPublicationModal';
import { TrainingTablePagination } from './TrainingTablePagination';

const LOADING_COLUMNS: TableSkeletonColumn[] = [
  {
    label: 'Version',
    headerClassName: 'w-20',
    skeletonClassName: 'h-4 w-8',
  },
  { label: 'Status', skeletonClassName: 'h-5 w-24' },
  {
    label: 'Uploaded',
    headerClassName: 'w-40',
    skeletonClassName: 'h-4 w-28',
  },
  {
    label: 'Size',
    headerClassName: 'w-24',
    skeletonClassName: 'h-4 w-12',
  },
  {
    label: 'Actions',
    headerClassName: 'w-32',
    skeletonClassName: 'h-8 w-20',
  },
  {
    label: 'Details',
    headerClassName: 'w-16',
    cellClassName: 'px-3',
    skeletonClassName: 'size-10',
  },
];

export function AdapterListTable({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useTrainedAdapters(agentId);
  const publication = useAdapterPublication(agentId);
  const adapters = data?.adapters ?? [];
  const { visibleItems, pagination } = useTrainingTablePagination(adapters, agentId);
  const bannerMessage = getPublishedAdapterWarning(data);

  return (
    <section aria-labelledby="uploaded-adapters-title" className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="uploaded-adapters-title" className={TYPOGRAPHY.headingSm}>
          Uploaded adapters
        </h2>
        {!isLoading && !isError && (
          <span className="text-xs leading-5 tabular-nums text-text-muted">
            {adapters.length} {adapters.length === 1 ? 'adapter' : 'adapters'}
          </span>
        )}
      </div>
      {isLoading ? (
        <TableSkeleton
          ariaLabel="Loading trained adapters"
          className={TABLE_STYLES.wrapper}
          tableClassName="min-w-[44rem] table-fixed [&_td]:py-2"
          rows={3}
          columns={LOADING_COLUMNS}
        />
      ) : isError ? (
        <p
          role="alert"
          className="rounded-md border border-border bg-destructive-soft px-4 py-5 text-sm text-destructive"
        >
          Failed to load trained adapters.
        </p>
      ) : adapters.length === 0 ? (
        <div className="flex items-start gap-3 rounded-md border border-border bg-surface px-4 py-5 sm:px-5">
          <Stack className="mt-0.5 size-5 shrink-0 text-text-muted" aria-hidden="true" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-text">No adapters uploaded yet.</p>
            <p className="text-sm leading-5 text-text-muted">
              Upload the trained adapter from the final notebook cell.
            </p>
          </div>
        </div>
      ) : (
        <>
          {bannerMessage ? <AdapterWarning message={bannerMessage} /> : null}
          <div className={TABLE_STYLES.wrapper}>
            <table
              className={cn(TABLE_STYLES.table, 'min-w-[44rem] table-fixed')}
              aria-label="Uploaded adapters"
            >
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-20')}>
                    Version
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Status
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-40')}>
                    Uploaded
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-24')}>
                    Size
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-32')}>
                    Actions
                  </th>
                  <th scope="col" className="w-16">
                    <span className="sr-only">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {visibleItems.map((adapter) => (
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
          <TrainingTablePagination label="Uploaded adapters" pagination={pagination} />
          {publication.error ? (
            <AdapterWarning message={getErrorMessage(publication.error)} />
          ) : null}
          {data && data.unrecognized_server_adapters.length > 0 ? (
            <details className="border-t border-border pt-4 text-sm text-text-muted">
              <summary className="w-fit cursor-pointer rounded-sm font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                Unrecognized files on the server ({data.unrecognized_server_adapters.length})
              </summary>
              <ul className="mt-2 list-disc space-y-1 pl-5 font-mono text-xs leading-5 [overflow-wrap:anywhere]">
                {data.unrecognized_server_adapters.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </details>
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

function AdapterWarning({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-md border border-destructive/20 bg-destructive-soft px-4 py-3 text-sm leading-5 text-destructive"
    >
      <Warning className="mt-1 size-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
