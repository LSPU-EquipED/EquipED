import { cn } from '@/shared/components/utils';
import type { ReferenceLibraryItem } from '../types';
import {
  formatDate,
  healthBadgeClass,
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

  return (
    <tr className="hover:bg-slate-50/50">
      <td className="py-3 px-4 align-top">
        <p
          className="text-sm font-semibold text-slate-900 truncate max-w-[16rem]"
          title={item.title}
        >
          {item.title}
        </p>
        {item.courseTitle ? (
          <p className="text-xs font-medium text-slate-500 truncate max-w-[16rem]">
            {item.courseTitle}
          </p>
        ) : null}
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-700">
          {referenceTypeLabels[item.sourceType] ?? item.sourceType}
        </span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-600">{item.courseCode ?? '—'}</span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-600">{item.academicYear ?? '—'}</span>
      </td>
      <td className="py-3 px-4 align-top">
        <span className="text-sm font-medium text-slate-600 truncate max-w-[10rem] block">
          {item.lessonTitle ?? '—'}
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
        <span className="text-sm font-medium text-slate-600">{formatDate(item.uploadedAt)}</span>
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
                : 'Rebuild Chroma vectors from stored chunks'
          }
          onPreview={onPreview}
          onRebuild={onRebuild}
          onDelete={onDelete}
        />
      </td>
    </tr>
  );
}
