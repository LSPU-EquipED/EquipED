import { CaretDown, CaretRight, User } from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { TABLE_STYLES, type StatusVariant } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';
import type { PreferenceLogItem } from '../types';
import { PreferenceDiffDrawer } from './PreferenceDiffDrawer';

function getActionVariant(action: string): StatusVariant {
  const normalized = action.toUpperCase();
  if (normalized === 'EDIT' || normalized === 'EDITED' || normalized === 'UPDATE') {
    return 'accent';
  }
  if (normalized === 'ACCEPT' || normalized === 'ACCEPTED' || normalized === 'APPROVE') {
    return 'success';
  }
  if (normalized === 'REJECT' || normalized === 'REJECTED' || normalized === 'DELETE') {
    return 'destructive';
  }
  return 'neutral';
}

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
  const hasDetails = Boolean(log.edited_json || log.notes);
  const score =
    log.edited_json &&
    typeof log.edited_json === 'object' &&
    'score' in log.edited_json
      ? log.edited_json.score
      : null;

  const justification =
    log.edited_json &&
    typeof log.edited_json === 'object' &&
    'justification' in log.edited_json
      ? String(log.edited_json.justification)
      : null;

  return (
    <>
      <tr className={cn(TABLE_STYLES.tr, isExpanded && 'bg-surface-subtle/50 transition-colors')}>
        {/* Left-side Toggle Caret */}
        <td className="py-3 px-3 text-center">
          {hasDetails ? (
            <button
              type="button"
              onClick={onToggle}
              className="inline-flex size-6 items-center justify-center rounded-xs text-text-muted hover:text-text hover:bg-surface-subtle cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label={isExpanded ? 'Hide Diff' : 'View Diff'}
            >
              {isExpanded ? (
                <CaretDown className="size-3.5 text-primary" />
              ) : (
                <CaretRight className="size-3.5 text-text-muted" />
              )}
            </button>
          ) : (
            <span className="inline-block size-6" />
          )}
        </td>

        {/* User ID */}
        <td className={cn(TABLE_STYLES.tdData, 'whitespace-nowrap')}>
          <div className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-text">
            <User className="size-3.5 text-text-muted shrink-0" />
            <span className="truncate max-w-[10rem]" title={log.user_id}>
              {log.user_id}
            </span>
          </div>
        </td>

        {/* Action Badge */}
        <td className={TABLE_STYLES.td}>
          <Badge variant={getActionVariant(log.action)} withDot>
            {log.action}
          </Badge>
        </td>

        {/* Evaluation ID */}
        <td className={cn(TABLE_STYLES.tdData, 'font-mono text-xs text-text-muted whitespace-nowrap')}>
          <span className="rounded-xs bg-surface-subtle border border-border px-1.5 py-0.5" title={log.evaluation_id}>
            {log.evaluation_id}
          </span>
        </td>

        {/* Details / Score Column: Only the clean score badge */}
        <td className={TABLE_STYLES.td}>
          {score !== null && score !== undefined ? (
            <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-xs bg-primary-soft text-primary border border-primary/20 text-xs font-bold font-mono tabular-nums">
              Score: {String(score)}
            </span>
          ) : (
            <span className="text-xs text-text-muted font-medium">—</span>
          )}
        </td>

        {/* Created Timestamp */}
        <td className={cn(TABLE_STYLES.tdData, 'text-right text-text-muted font-medium text-xs whitespace-nowrap font-mono tabular-nums')}>
          {new Date(log.created_at).toLocaleString()}
        </td>
      </tr>

      {/* Expanded Diff Drawer */}
      {isExpanded && hasDetails ? (
        <PreferenceDiffDrawer
          log={log}
          score={score}
          justification={justification}
        />
      ) : null}
    </>
  );
}
