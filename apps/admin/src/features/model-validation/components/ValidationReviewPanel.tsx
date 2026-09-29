import { X } from '@phosphor-icons/react';
import { Badge } from '@equiped/ui';
import type { ModelValidationItem } from '../types';
import { adapterFallbackNotices, formatTimestamp, itemModelLabel } from '../utils/helpers';
import { ValidationDetail } from './ValidationDetail';

export function ValidationReviewPanel({
  item,
  onClose,
}: {
  item: ModelValidationItem;
  onClose: () => void;
}) {
  return (
    <aside
      role="region"
      aria-label={`Validation details for ${item.document_title ?? 'Untitled SLM'}`}
      className="min-w-0 border-t border-border bg-canvas lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto lg:border-l lg:border-t-0"
    >
      <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-border bg-canvas px-5 py-4 sm:px-6">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-primary">Validation review</p>
          <h2 className="mt-1 truncate text-lg font-semibold text-text">
            {item.document_title ?? 'Untitled SLM'}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
            <Badge
              variant={
                item.status === 'COMPLETED'
                  ? 'success'
                  : item.status === 'FAILED'
                    ? 'destructive'
                    : 'warning'
              }
              withDot
            >
              {item.status.charAt(0) + item.status.slice(1).toLowerCase()}
            </Badge>
            <span className="font-mono tabular-nums">{formatTimestamp(item.created_at)}</span>
            {itemModelLabel(item) ? (
              <span className="rounded-xs border border-border bg-surface-subtle px-1.5 py-0.5 font-semibold text-text">
                {itemModelLabel(item)}
              </span>
            ) : null}
            {item.partial_without_curriculum ? (
              <span className="font-medium text-warning">Partial run</span>
            ) : null}
          </div>
          {adapterFallbackNotices(item.adapter_resolution).map((notice) => (
            <p key={notice} className="mt-2 text-[11px] font-medium text-warning">
              {notice}
            </p>
          ))}
        </div>
        <button
          type="button"
          aria-label="Close validation details"
          onClick={onClose}
          className="inline-flex size-9 shrink-0 items-center justify-center rounded-sm border border-border bg-surface text-text-muted transition-colors hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </header>
      <div className="p-5 sm:p-6">
        <ValidationDetail
          id={`validation-detail-${item.validation_id}`}
          validationId={item.validation_id}
          fallbackCriteria={item.criterion_scores}
          boundForms={item.bound_forms}
          partialWithoutCurriculum={item.partial_without_curriculum}
          overallStatus={item.status}
          errorMessage={item.error_message}
          isExpanded
        />
      </div>
    </aside>
  );
}
