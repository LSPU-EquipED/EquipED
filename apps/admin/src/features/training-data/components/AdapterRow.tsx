import { useId, useState } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { Badge, Button, CollapsibleRow, TABLE_STYLES, TYPOGRAPHY, cn } from '@equiped/ui';
import type { TrainedAdapterItem } from '../types';
import { AdapterGgufPanel } from './AdapterGgufPanel';
import { AdapterLoadHint } from './AdapterLoadHint';
import { formatSize } from '../utils/trainingData.utils';
import { TrainingRecordMetadata } from './TrainingRecordMetadata';
import { TrainingSummaryPanel } from './TrainingSummaryPanel';

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
              title={
                adapter.loaded !== true
                  ? 'Not loaded on the model server. Ask IT staff to add it first.'
                  : undefined
              }
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
            aria-label={`${expanded ? 'Hide' : 'Show'} details for fine-tuned model v${adapter.version}`}
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
        <TrainingRecordMetadata entries={[['Added', uploaded.toLocaleString()]]} />
        <p className="mt-3 text-xs leading-5 text-text-muted">
          Whether this fine-tuned model scores better is shown on the Model Validation page.
        </p>
        <details className="mt-3 border-t border-border pt-3 text-sm text-text-muted">
          <summary className="cursor-pointer text-[13px] font-medium text-text">
            For IT staff
          </summary>
          <div className="mt-3">
            <TrainingSummaryPanel summary={adapter.training_summary} />
          </div>
          <div className="mt-3">
            <TrainingRecordMetadata
              entries={[
                ['File name', adapter.gguf_filename],
                ['Training run ID', adapter.job_id],
                ['File SHA-256', adapter.file_sha256],
                ['Fine-tuned model ID', adapter.adapter_id],
              ]}
            />
          </div>
          <AdapterGgufPanel adapter={adapter} published={adapter.published} />
          {adapter.loaded === false && (
            <div className="mt-3 space-y-1.5 border-t border-border pt-3">
              <p className="text-[13px] font-medium leading-5 text-text">Add to the model server</p>
              <AdapterLoadHint filename={adapter.gguf_filename} />
            </div>
          )}
        </details>
      </CollapsibleRow>
    </>
  );
}
