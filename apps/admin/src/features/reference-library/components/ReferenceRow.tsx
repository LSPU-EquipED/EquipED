import { CheckCircle, Clock, WarningCircle } from '@phosphor-icons/react';
import { cn } from '@equiped/ui';
import type { ReferenceLibraryItem } from '../types';
import {
  formatDate,
  processingStatusClass,
  referenceTypeLabels,
} from '../utils/helpers';
import { RowActionButtons } from './RowActionButtons';

interface ReferenceRowProps {
  item: ReferenceLibraryItem;
  isBusy: boolean;
  isDeleting: boolean;
  isRebuilding: boolean;
  onPreview: () => void;
  onRebuild: () => void;
  onDelete: () => void;
}

export function ReferenceRow({
  item,
  isBusy,
  isDeleting,
  isRebuilding,
  onPreview,
  onRebuild,
  onDelete,
}: ReferenceRowProps) {
  const canRebuild = item.chunkCount > 0 && !item.chromaAvailable;
  const StatusIcon = item.processingStatus === 'PROCESSED'
    ? CheckCircle
    : item.processingStatus === 'FAILED'
      ? WarningCircle
      : Clock;

  return (
    <tr className="transition-colors hover:bg-surface-subtle/70">
      <td className="px-4 py-4 align-top">
        <div className="min-w-[20rem]">
          <p className="max-w-[28rem] break-words text-sm font-medium leading-relaxed text-text" title={item.title}>
            {item.title}
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-text-muted">
            <span>{referenceTypeLabels[item.sourceType] || item.sourceType}</span>
            {item.courseTitle ? (
              <>
                <span aria-hidden="true">·</span>
                <span>{item.courseTitle}</span>
              </>
            ) : null}
            {item.lessonTitle ? (
              <>
                <span aria-hidden="true">·</span>
                <span>{item.lessonTitle}</span>
              </>
            ) : null}
          </p>
        </div>
      </td>
      <td className="px-4 py-4 align-top">
        <div className="space-y-1 text-sm">
          <p className="font-medium text-text">{item.program ?? 'Institutional'}</p>
          <p className="text-xs text-text-muted">
            {[item.courseCode, item.academicYear].filter(Boolean).join(' · ') || 'General reference'}
          </p>
        </div>
      </td>
      <td className="px-4 py-4 align-top">
        <div className="min-w-[10rem] space-y-1.5">
          <span className={cn('inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-xs font-medium', processingStatusClass(item.processingStatus))}>
            <StatusIcon className="size-3.5" aria-hidden="true" />
            {item.processingStatus === 'PROCESSED' ? 'Processed' : item.processingStatus}
          </span>
          <p className="text-xs text-text-muted">
            <span className="tabular-nums">{item.chunkCount}</span>{' '}
            chunks · <span>{item.chromaAvailable ? 'Indexed' : 'Not indexed'}</span>
          </p>
          {!item.fileExists ? <p className="text-xs font-semibold text-destructive">File missing</p> : null}
        </div>
      </td>
      <td className="px-4 py-4 align-top">
        <span className="whitespace-nowrap text-xs tabular-nums text-text-muted">{formatDate(item.uploadedAt)}</span>
      </td>
      <td className="py-3 px-4 align-top text-right">
        <RowActionButtons
          canRebuild={canRebuild}
          isBusy={isBusy}
          isDeleting={isDeleting}
          isRebuilding={isRebuilding}
          rebuildTooltip={
            item.chromaAvailable
              ? 'Search index is ready'
              : item.chunkCount === 0
                ? 'No chunks available to rebuild'
                : 'Rebuild local search index from stored chunks'
          }
          onPreview={onPreview}
          onRebuild={onRebuild}
          onDelete={onDelete}
        />
      </td>
    </tr>
  );
}
