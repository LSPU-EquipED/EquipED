import { useId, useState } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { Badge, Button, CollapsibleRow, TABLE_STYLES, TYPOGRAPHY, cn } from '@equiped/ui';
import type { TrainedAdapterItem } from '../types';
import { AdapterLoadHint } from './AdapterLoadHint';
import { formatSize } from '../utils/trainingData.utils';
import { TrainingRecordMetadata } from './TrainingRecordMetadata';

function loadLabel(loaded: boolean | null) {
  if (loaded === true) return 'Loaded';
  if (loaded === false) return 'Not loaded';
  return 'Unknown';
}

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
        <td className={cn(TYPOGRAPHY.dataMd, 'px-4 py-2')}>v{adapter.version}</td>
        <td className="px-4 py-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {adapter.published ? (
              <Badge
                variant="info"
                className="border-primary/30 bg-primary-soft tracking-normal text-primary"
              >
                Published
              </Badge>
            ) : null}
            <Badge variant="neutral" className="tracking-normal">
              {loadLabel(adapter.loaded)}
            </Badge>
          </div>
        </td>
        <td className={cn(TYPOGRAPHY.dataMd, 'px-4 py-2')}>
          <time dateTime={adapter.created_at} className="block">
            {uploaded.toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </time>
        </td>
        <td className={cn(TYPOGRAPHY.dataMd, 'px-4 py-2')}>{formatSize(adapter.size_bytes)}</td>
        <td className="px-4 py-2">
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
        <td className="px-3 py-2 text-right">
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
      <CollapsibleRow id={detailsId} isExpanded={expanded} colSpan={6} innerClassName="px-4 py-3">
        <TrainingRecordMetadata
          entries={[
            ['Source run', adapter.job_id],
            ['File SHA-256', adapter.file_sha256],
            ['Adapter ID', adapter.adapter_id],
            ['Filename', adapter.gguf_filename],
            ['Uploaded', uploaded.toLocaleString()],
          ]}
        />
        {adapter.loaded === false && (
          <div className="mt-3 space-y-1.5 border-t border-border pt-3">
            <p className="text-[13px] font-medium leading-5 text-text">Load on the model server</p>
            <AdapterLoadHint filename={adapter.gguf_filename} />
          </div>
        )}
      </CollapsibleRow>
    </>
  );
}
