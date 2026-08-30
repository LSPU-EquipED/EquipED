import { useState } from 'react';
import { ChevronDown, ChevronRight, FileText, Loader2 } from 'lucide-react';
import { Badge } from '@/shared/components/Badge';
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES, type StatusVariant } from '@/shared/constants/theme';
import { usePreferenceLogs } from '../hooks/usePreferenceLogs';
import type { PreferenceLogItem } from '../types';

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

export function PreferenceLogTable() {
  const { data, isLoading, isError } = usePreferenceLogs();
  const [expandedLogIds, setExpandedLogIds] = useState<Set<string>>(new Set());

  const toggleExpand = (logId: string) => {
    setExpandedLogIds((prev) => {
      const next = new Set(prev);
      if (next.has(logId)) {
        next.delete(logId);
      } else {
        next.add(logId);
      }
      return next;
    });
  };

  return (
    <section className="grid gap-4">
      <div className={TABLE_STYLES.wrapper}>
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-text-muted font-medium text-sm">
            <Loader2 className="size-5 animate-spin" /> Loading preference logs...
          </div>
        ) : isError ? (
          <div className="py-10 text-center text-destructive font-semibold text-sm">
            Failed to load preference logs.
          </div>
        ) : !data?.items.length ? (
          <div className="py-10 text-center text-text-muted font-medium text-sm">
            No preference logs yet.
          </div>
        ) : (
          <table className={TABLE_STYLES.table}>
            <thead className={TABLE_STYLES.thead}>
              <tr>
                <th className="py-3 px-4 w-10 text-center" />
                <th className={TABLE_STYLES.th}>User ID</th>
                <th className={TABLE_STYLES.th}>Action</th>
                <th className={TABLE_STYLES.th}>Evaluation ID</th>
                <th className={TABLE_STYLES.th}>Details / Score</th>
                <th className={cn(TABLE_STYLES.th, 'text-right')}>Created</th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {data.items.map((log: PreferenceLogItem) => {
                const isExpanded = expandedLogIds.has(log.log_id);
                const hasDetails = !!log.edited_json || !!log.notes;
                const score =
                  log.edited_json && typeof log.edited_json === 'object' && 'score' in log.edited_json
                    ? log.edited_json.score
                    : null;

                return (
                  <LogRow
                    key={log.log_id}
                    log={log}
                    isExpanded={isExpanded}
                    hasDetails={hasDetails}
                    score={score}
                    onToggle={() => toggleExpand(log.log_id)}
                  />
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

interface LogRowProps {
  log: PreferenceLogItem;
  isExpanded: boolean;
  hasDetails: boolean;
  score: unknown;
  onToggle: () => void;
}

function LogRow({ log, isExpanded, hasDetails, score, onToggle }: LogRowProps) {
  const justification =
    log.edited_json && typeof log.edited_json === 'object' && 'justification' in log.edited_json
      ? String(log.edited_json.justification)
      : null;

  return (
    <>
      <tr className={cn(TABLE_STYLES.tr, isExpanded && 'bg-surface-subtle/50')}>
        <td className="py-3 px-4 text-center">
          {hasDetails ? (
            <button
              type="button"
              onClick={onToggle}
              className="inline-flex size-6 items-center justify-center rounded-xs text-text-muted hover:text-text hover:bg-surface-subtle cursor-pointer transition-colors"
              aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
            >
              {isExpanded ? (
                <ChevronDown className="size-4" />
              ) : (
                <ChevronRight className="size-4" />
              )}
            </button>
          ) : null}
        </td>
        <td className={cn(TABLE_STYLES.tdData, 'font-mono text-xs text-text')}>
          {log.user_id}
        </td>
        <td className={TABLE_STYLES.td}>
          <Badge variant={getActionVariant(log.action)}>
            {log.action}
          </Badge>
        </td>
        <td className={cn(TABLE_STYLES.tdData, 'font-mono text-xs text-text')}>
          {log.evaluation_id}
        </td>
        <td className={TABLE_STYLES.td}>
          <div className="flex items-center gap-2">
            {score !== null && score !== undefined ? (
              <Badge variant="accent" className="tabular-nums font-semibold">
                Score: {String(score)}
              </Badge>
            ) : null}
            {hasDetails ? (
              <button
                type="button"
                onClick={onToggle}
                className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline cursor-pointer"
              >
                <FileText className="size-3.5" />
                <span>{isExpanded ? 'Hide Diff' : 'View Diff'}</span>
              </button>
            ) : (
              <span className="text-xs text-text-muted">—</span>
            )}
          </div>
        </td>
        <td className={cn(TABLE_STYLES.tdData, 'text-right text-text-muted font-medium text-xs')}>
          {new Date(log.created_at).toLocaleString()}
        </td>
      </tr>
      {isExpanded && hasDetails ? (
        <tr className="bg-surface-subtle/30">
          <td colSpan={6} className="px-6 py-4 border-b border-border">
            <div className="rounded-md border border-border bg-surface p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-border pb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-text">
                  Preference Correction Diff
                </span>
                <span className="text-xs font-mono text-text-muted tabular-nums">
                  Log ID: {log.log_id}
                </span>
              </div>

              {score !== null && score !== undefined ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                    Corrected Criterion Score:
                  </span>
                  <span className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-xs bg-accent-soft text-accent-foreground border border-accent/30 text-xs font-bold tabular-nums">
                    {String(score)}
                  </span>
                </div>
              ) : null}

              {justification ? (
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                    Reviewer Justification:
                  </span>
                  <p className="text-xs font-medium text-text bg-surface-subtle p-3 rounded-xs border border-border leading-relaxed whitespace-pre-wrap">
                    {justification}
                  </p>
                </div>
              ) : null}

              {log.notes ? (
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                    Reviewer Notes:
                  </span>
                  <p className="text-xs font-medium text-text bg-surface-subtle p-3 rounded-xs border border-border leading-relaxed whitespace-pre-wrap">
                    {log.notes}
                  </p>
                </div>
              ) : null}

              {log.edited_json && (!score && !justification) ? (
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                    Edited Payload:
                  </span>
                  <pre className="text-xs font-mono text-text bg-surface-subtle p-3 rounded-xs border border-border overflow-x-auto leading-relaxed">
                    {JSON.stringify(log.edited_json, null, 2)}
                  </pre>
                </div>
              ) : null}
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}
