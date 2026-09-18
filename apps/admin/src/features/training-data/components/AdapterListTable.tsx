import { Package, Warning } from '@phosphor-icons/react';
import { CARD_STYLES, TABLE_STYLES, TableSkeleton, cn } from '@equiped/ui';
import { useTrainedAdapters } from '../hooks/useTrainedAdapters';
import type { TrainedAdapterItem } from '../types';
import { formatSize } from '../utils/trainingData.utils';

export function AdapterListTable({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useTrainedAdapters(agentId);
  const adapters = data?.adapters ?? [];

  return (
    <div className={CARD_STYLES.ledger}>
      <div className={CARD_STYLES.header}>
        <div className="flex items-center gap-2">
          <Package className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-text">
            Trained Adapters
          </h2>
        </div>
      </div>

      {isLoading ? (
        <TableSkeleton
          ariaLabel="Loading trained adapters"
          columns={[
            { label: 'Version', headerClassName: 'w-20', skeletonClassName: 'h-4 w-8' },
            { label: 'Uploaded', skeletonClassName: 'h-4 w-32' },
            { label: 'Size', skeletonClassName: 'h-4 w-16' },
            { label: 'Hash', skeletonClassName: 'h-4 w-24' },
            { label: 'Source Job', skeletonClassName: 'h-4 w-40' },
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
            Once a Colab training run pushes an adapter back, it will appear here with a link
            to the dataset snapshot that trained it.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className={TABLE_STYLES.table}>
            <thead className={TABLE_STYLES.thead}>
              <tr>
                <th className={cn(TABLE_STYLES.th, 'w-20')}>Version</th>
                <th className={TABLE_STYLES.th}>Uploaded</th>
                <th className={TABLE_STYLES.th}>Size</th>
                <th className={TABLE_STYLES.th}>Hash</th>
                <th className={TABLE_STYLES.th}>Source Job</th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {adapters.map((adapter: TrainedAdapterItem) => (
                <tr key={adapter.adapter_id} className={TABLE_STYLES.tr}>
                  <td className={cn(TABLE_STYLES.tdData, 'font-semibold')}>v{adapter.version}</td>
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
