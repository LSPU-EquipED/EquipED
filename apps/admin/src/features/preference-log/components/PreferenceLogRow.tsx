import { useId } from 'react';
import { CaretDown, CaretRight } from '@phosphor-icons/react';
import {
  Badge,
  Button,
  TABLE_STYLES,
  cn,
  type StatusVariant,
} from '@equiped/ui';
import type { PreferenceLogItem } from '../types';
import { PreferenceLogDetails } from './PreferenceLogDetails';

const ACTION_PRESENTATION: Record<
  string,
  { label: string; variant: StatusVariant }
> = {
  EDIT: { label: 'Edited', variant: 'accent' },
  ACCEPT: { label: 'Accepted', variant: 'success' },
  REJECT: { label: 'Rejected', variant: 'destructive' },
  ITEM_ACCEPT: { label: 'Item accepted', variant: 'success' },
  ITEM_REJECT: { label: 'Item rejected', variant: 'destructive' },
};

interface PreferenceLogRowProps {
  log: PreferenceLogItem;
  isExpanded: boolean;
  onToggle: () => void;
}

export function PreferenceLogRow({
  log,
  isExpanded,
  onToggle,
}: PreferenceLogRowProps) {
  const detailsId = useId();
  const score = log.edited_json?.score;
  const action = ACTION_PRESENTATION[log.action.toUpperCase()];
  const loggedAt = new Date(log.created_at);
  const detailsLabel = `${isExpanded ? 'Hide' : 'View'} details for log ${log.log_id}`;

  return (
    <>
      <tr className={cn(TABLE_STYLES.tr, isExpanded && 'bg-surface-subtle/50')}>
        <td className="px-2 py-2 text-center">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onToggle}
            aria-label={detailsLabel}
            title={detailsLabel}
            aria-expanded={isExpanded}
            aria-controls={isExpanded ? detailsId : undefined}
          >
            {isExpanded ? (
              <CaretDown className="size-4" aria-hidden="true" />
            ) : (
              <CaretRight className="size-4" aria-hidden="true" />
            )}
          </Button>
        </td>
        <td className={TABLE_STYLES.tdData}>
          <span
            className="block max-w-40 truncate font-medium"
            title={log.user_id}
          >
            {log.user_id}
          </span>
        </td>
        <td className={TABLE_STYLES.td}>
          <Badge
            variant={action?.variant ?? 'neutral'}
            className="whitespace-nowrap tracking-normal"
          >
            {action?.label ?? log.action}
          </Badge>
        </td>
        <td className={cn(TABLE_STYLES.tdData, 'text-text-muted')}>
          <span className="block max-w-40 truncate" title={log.evaluation_id}>
            {log.evaluation_id}
          </span>
        </td>
        <td className={cn(TABLE_STYLES.tdData, 'text-right font-medium')}>
          {typeof score === 'number' || typeof score === 'string' ? (
            score
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </td>
        <td className={cn(TABLE_STYLES.tdData, 'text-right whitespace-nowrap')}>
          <time dateTime={log.created_at}>
            <span className="block">
              {loggedAt.toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </span>
            <span className="block text-xs text-text-muted">
              {loggedAt.toLocaleTimeString(undefined, {
                hour: 'numeric',
                minute: '2-digit',
                second: '2-digit',
              })}
            </span>
          </time>
        </td>
      </tr>
      {isExpanded ? <PreferenceLogDetails id={detailsId} log={log} /> : null}
    </>
  );
}
