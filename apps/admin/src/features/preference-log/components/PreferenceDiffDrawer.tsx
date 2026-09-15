import type { PreferenceLogItem } from '../types';

interface PreferenceDiffDrawerProps {
  log: PreferenceLogItem;
  score: unknown;
  justification: string | null;
}

export function PreferenceDiffDrawer({
  log,
  score,
  justification,
}: PreferenceDiffDrawerProps) {
  return (
    <tr className="bg-surface-subtle/30">
      <td colSpan={6} className="p-4 sm:p-5 border-b border-border">
        <div className="rounded-md border border-border bg-surface p-5 space-y-4 shadow-none">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-primary" />
              <span className="text-xs font-bold uppercase tracking-wider text-text">
                Preference Correction Diff
              </span>
            </div>
            <span className="text-xs font-mono text-text-muted tabular-nums rounded-xs bg-surface-subtle border border-border px-2 py-0.5">
              Log ID: {log.log_id}
            </span>
          </div>

          {score !== null && score !== undefined ? (
            <div className="flex items-center gap-2.5 text-xs">
              <span className="font-semibold text-text-muted">
                Corrected Criterion Score:
              </span>
              <span className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-xs bg-primary-soft text-primary border border-primary/20 text-xs font-bold tabular-nums font-mono">
                {String(score)}
              </span>
            </div>
          ) : null}

          {justification ? (
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                Reviewer Justification:
              </span>
              <div className="border-l-4 border-primary/40 bg-surface-subtle p-3.5 rounded-sm border border-border/80">
                <p className="text-xs font-medium text-text leading-relaxed whitespace-pre-wrap">
                  {justification}
                </p>
              </div>
            </div>
          ) : null}

          {log.notes ? (
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                Reviewer Notes:
              </span>
              <p className="text-xs font-medium text-text bg-surface-subtle p-3.5 rounded-sm border border-border leading-relaxed whitespace-pre-wrap">
                {log.notes}
              </p>
            </div>
          ) : null}

          {log.edited_json && (!score && !justification) ? (
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                Edited Payload:
              </span>
              <pre className="text-xs font-mono text-text bg-surface-subtle p-3.5 rounded-sm border border-border overflow-x-auto leading-relaxed">
                {JSON.stringify(log.edited_json, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      </td>
    </tr>
  );
}
