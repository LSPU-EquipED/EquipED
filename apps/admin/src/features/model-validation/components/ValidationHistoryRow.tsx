import { CaretRight, FilePdf } from '@phosphor-icons/react';
import { Badge, Button, cn } from '@equiped/ui';
import type { ModelValidationItem } from '../types';
import { agentLabel, formatTimestamp, itemModelLabel } from '../utils/helpers';

type ValidationHistoryRowProps = {
  item: ModelValidationItem;
  isExpanded: boolean;
  comparedCount: number;
  exactMatches: number;
  onToggle: () => void;
};

function formatMaeBadge(mae: number | null | undefined) {
  if (mae == null) return <span className="text-text-muted font-medium">—</span>;
  const isExcellent = mae <= 0.25;
  const isModerate = mae <= 0.5;

  return (
    <span
      className={cn(
        'inline-block px-1.5 py-0.5 rounded-xs font-mono font-bold text-xs tabular-nums border',
        isExcellent
          ? 'bg-success-soft text-success border-success/30'
          : isModerate
            ? 'bg-warning-soft text-warning border-warning/30'
            : 'bg-destructive-soft text-destructive border-destructive/30',
      )}
    >
      {mae.toFixed(2)}
    </span>
  );
}

export function ValidationHistoryRow({
  item,
  isExpanded,
  comparedCount,
  exactMatches,
  onToggle,
}: ValidationHistoryRowProps) {
  return (
    <tr className={cn(isExpanded && 'bg-primary-soft/40 transition-colors')}>
      <td className="px-3 py-3 font-semibold text-text sm:px-4">
        <div className="flex items-start gap-2.5">
          <FilePdf className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          <div className="min-w-0">
            <div
              className="truncate text-sm font-semibold text-text"
              title={item.document_title ?? 'Untitled SLM'}
            >
              {item.document_title ?? 'Untitled SLM'}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-text-muted">
              <span className="font-mono tabular-nums">{formatTimestamp(item.created_at)}</span>
              {itemModelLabel(item) ? (
                <span
                  className={cn(
                    'rounded-xs border px-1.5 py-0.5 text-[10px] font-semibold',
                    item.model_variant === 'adapter'
                      ? 'border-primary/20 bg-primary-soft text-primary'
                      : 'border-border bg-surface-subtle text-text-muted',
                  )}
                >
                  {itemModelLabel(item)}
                </span>
              ) : null}
              <span className={item.partial_without_curriculum ? 'font-medium text-warning' : ''}>
                {item.partial_without_curriculum ? 'Partial run' : 'Full reference set'}
              </span>
              {item.bound_forms?.length ? (
                <>
                  <span>{item.bound_forms.length} rubric snapshots</span>
                  <span className="sr-only">Bound rubric revisions:</span>
                  {item.bound_forms.map((form) => (
                    <span
                      key={form.agent_id}
                      className="rounded-xs border border-border bg-surface-subtle px-1.5 py-0.5 font-semibold text-text"
                      title={`${agentLabel(form.agent_id)}: ${form.rubric_set_id}`}
                    >
                      {form.agent_id.toUpperCase()} v{form.rubric_version}
                    </span>
                  ))}
                </>
              ) : null}
            </div>
          </div>
        </div>
      </td>

      <td className="px-3 py-3 align-top whitespace-nowrap sm:px-4">
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
      </td>

      <td className="px-3 py-3 text-right align-top whitespace-nowrap sm:px-4">
        {comparedCount ? (
          <div className="inline-flex flex-col items-end gap-0.5 font-mono tabular-nums">
            <span className="text-sm font-semibold text-text">
              {exactMatches}/{comparedCount}
            </span>
            <span className="text-[11px] text-text-muted">
              {((exactMatches / comparedCount) * 100).toFixed(0)}% exact
            </span>
          </div>
        ) : (
          <span className="text-text-muted">—</span>
        )}
      </td>

      <td className="px-3 py-3 text-right align-top sm:px-4">
        <div className="inline-flex max-w-full flex-col items-end gap-1 text-[11px] tabular-nums">
          <span className="inline-flex items-center gap-1.5 font-mono">
            <span className="text-text-muted">MAE</span>
            {formatMaeBadge(item.absolute_error)}
          </span>
          <span className="font-mono text-text-muted">
            {item.latency_seconds == null ? '—' : `${item.latency_seconds.toFixed(2)} s`}
            <span className="mx-1 text-border">·</span>
            {item.toxicity_score == null
              ? 'tox —'
              : `tox ${(item.toxicity_score * 100).toFixed(1)}%`}
          </span>
        </div>
      </td>

      <td className="px-3 py-3 text-right align-top sm:px-4">
        {item.status === 'COMPLETED' ||
        item.status === 'FAILED' ||
        item.criterion_scores.length > 0 ? (
          <Button
            type="button"
            variant={isExpanded ? 'primary' : 'secondary'}
            size="sm"
            onClick={onToggle}
            aria-expanded={isExpanded}
            aria-controls={isExpanded ? `validation-detail-${item.validation_id}` : undefined}
            aria-label={`${isExpanded ? 'Close' : 'Open'} evaluation for ${item.document_title ?? 'Untitled SLM'}`}
            className="h-8 gap-1.5 px-2.5 text-xs font-semibold"
          >
            <CaretRight
              className={cn('size-3.5 transition-transform', isExpanded && 'rotate-90')}
              aria-hidden="true"
            />
            <span>{isExpanded ? 'Open' : 'Review'}</span>
          </Button>
        ) : item.error_message ? (
          <span className="text-xs font-semibold text-destructive">{item.error_message}</span>
        ) : (
          <span className="text-text-muted">—</span>
        )}
      </td>
    </tr>
  );
}
