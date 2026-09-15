import { cn } from '@/shared/components/utils';
import type { PolicyLibraryItem } from '../types';
import {
  formatDate,
  healthBadgeClass,
  isPolicyArea,
  policyAreaLabelMap,
  processingStatusClass,
} from '../utils/helpers';
import { RowActionButtons } from './RowActionButtons';

interface PolicyRowProps {
  item: PolicyLibraryItem;
  isBusy: boolean;
  isDeleting: boolean;
  isRebuilding: boolean;
  onPreview: () => void;
  onRebuild: () => void;
  onDelete: () => void;
}

export function PolicyRow({
  item,
  isBusy,
  isDeleting,
  isRebuilding,
  onPreview,
  onRebuild,
  onDelete,
}: PolicyRowProps) {
  const canRebuild = item.chunkCount > 0 && !item.chromaAvailable;
  const areaLabel = isPolicyArea(item.policyArea)
    ? policyAreaLabelMap[item.policyArea]
    : (item.policyArea ?? '—');

  return (
    <tr className="hover:bg-surface-subtle/70 transition-colors">
      <td className="py-3 px-4 align-top">
        <p
          className="text-sm font-semibold text-text truncate max-w-[18rem]"
          title={item.title}
        >
          {item.title}
        </p>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="inline-flex items-center rounded-sm border border-border bg-surface-subtle px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-text">
          {areaLabel}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider',
            processingStatusClass(item.processingStatus),
          )}
        >
          {item.processingStatus}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold',
            healthBadgeClass(item.fileExists),
          )}
        >
          {item.fileExists ? 'Found' : 'Missing'}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold tabular-nums',
            healthBadgeClass(item.chunkCount > 0),
          )}
        >
          {item.chunkCount}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span
          className={cn(
            'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold',
            healthBadgeClass(item.chromaAvailable),
          )}
        >
          {item.chromaAvailable ? 'Indexed' : 'Not indexed'}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-text-muted tabular-nums">{formatDate(item.uploadedAt)}</span>
      </td>
      <td className="py-3 px-4 align-top text-right">
        <RowActionButtons
          canRebuild={canRebuild}
          isBusy={isBusy}
          isDeleting={isDeleting}
          isRebuilding={isRebuilding}
          rebuildTooltip={
            item.chromaAvailable
              ? 'Chroma vectors already present'
              : item.chunkCount === 0
                ? 'No chunks available to rebuild'
                : 'Rebuild Chroma vectors from stored policy chunks'
          }
          onPreview={onPreview}
          onRebuild={onRebuild}
          onDelete={onDelete}
        />
      </td>
    </tr>
  );
}
