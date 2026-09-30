import { useId, useState } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { Button, CollapsibleRow, TABLE_STYLES, cn } from '@equiped/ui';
import type { TrainedAdapterItem } from '../types';
import { AdapterLoadHint } from './AdapterLoadHint';
import { formatSize } from '../utils/trainingData.utils';

function loadLabel(loaded: boolean | null) {
  if (loaded === true) return 'Loaded';
  if (loaded === false) return 'Not loaded';
  return 'Unknown';
}

const BADGE = 'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold';

export function AdapterRow({
  adapter,
  onPublish,
  onUnpublish,
}: {
  adapter: TrainedAdapterItem;
  onPublish: () => void;
  onUnpublish: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const uploaded = new Date(adapter.created_at);

  return (
    <>
      <tr className={TABLE_STYLES.tr}>
        <td className={cn(TABLE_STYLES.tdData, 'font-medium')}>v{adapter.version}</td>
        <td className={TABLE_STYLES.tdData}>
          <div className="flex flex-wrap items-center gap-1.5">
            {adapter.published ? (
              <span className={cn(BADGE, 'border-primary/30 bg-primary-soft text-primary')}>
                Published
              </span>
            ) : null}
            <span className={cn(BADGE, 'border-border bg-surface-subtle text-text-muted')}>
              {loadLabel(adapter.loaded)}
            </span>
          </div>
          {adapter.loaded === false ? <AdapterLoadHint filename={adapter.gguf_filename} /> : null}
        </td>
        <td className={TABLE_STYLES.tdData}>
          <time dateTime={adapter.created_at} className="block">
            {uploaded.toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </time>
          <span className="text-sm text-text-muted">
            {uploaded.toLocaleTimeString(undefined, {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </td>
        <td className={TABLE_STYLES.tdData}>{formatSize(adapter.size_bytes)}</td>
        <td className={TABLE_STYLES.tdData}>
          {adapter.published ? (
            <Button variant="secondary" size="sm" onClick={onUnpublish}>
              Unpublish
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              disabled={adapter.loaded !== true}
              onClick={onPublish}
            >
              Publish
            </Button>
          )}
        </td>
        <td className="pr-3 text-right">
          <Button
            variant="ghost"
            size="icon"
            title={expanded ? 'Hide details' : 'Show details'}
            aria-label={`${expanded ? 'Hide' : 'Show'} details for adapter v${adapter.version}`}
            aria-expanded={expanded}
            aria-controls={detailsId}
            onClick={() => setExpanded(!expanded)}
          >
            <CaretDown
              className={cn(
                'size-4 transition-transform duration-180 motion-reduce:transition-none',
                expanded && 'rotate-180',
              )}
              aria-hidden="true"
            />
          </Button>
        </td>
      </tr>
      <CollapsibleRow id={detailsId} isExpanded={expanded} colSpan={6} innerClassName="p-4 sm:p-5">
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          {[
            ['Source run', adapter.job_id],
            ['File SHA-256', adapter.file_sha256],
            ['Adapter ID', adapter.adapter_id],
          ].map(([label, value]) => (
            <div key={label} className="min-w-0 space-y-1">
              <dt className="text-text-muted">{label}</dt>
              <dd className="break-words font-medium text-text [overflow-wrap:anywhere]">
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </CollapsibleRow>
    </>
  );
}
