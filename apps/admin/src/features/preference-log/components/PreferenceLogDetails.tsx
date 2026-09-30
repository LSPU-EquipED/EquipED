import type { PreferenceLogItem } from '../types';

interface PreferenceLogDetailsProps {
  id: string;
  log: PreferenceLogItem;
}

export function PreferenceLogDetails({ id, log }: PreferenceLogDetailsProps) {
  const justification = log.edited_json?.justification;

  return (
    <tr id={id} className="border-b border-border bg-surface-subtle/30">
      <td colSpan={6} className="px-5 py-5 sm:px-6">
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text">Review details</h3>
          <dl className="grid gap-4 text-sm sm:grid-cols-3">
            {[
              ['Log ID', log.log_id],
              ['Reviewer ID', log.user_id],
              ['Evaluation ID', log.evaluation_id],
            ].map(([label, value]) => (
              <div key={label} className="min-w-0 space-y-1">
                <dt className="text-text-muted">{label}</dt>
                <dd className="break-all text-text tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          {(typeof justification === 'string' && justification) || log.notes ? (
            <div className="grid gap-4 border-t border-border pt-4 text-sm sm:grid-cols-2">
              {typeof justification === 'string' && justification ? (
                <div className="min-w-0 space-y-1">
                  <h4 className="font-medium text-text-muted">Justification</h4>
                  <p className="whitespace-pre-wrap break-words leading-relaxed text-text">
                    {justification}
                  </p>
                </div>
              ) : null}
              {log.notes ? (
                <div className="min-w-0 space-y-1">
                  <h4 className="font-medium text-text-muted">Notes</h4>
                  <p className="whitespace-pre-wrap break-words leading-relaxed text-text">
                    {log.notes}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}
          {log.edited_json ? (
            <details className="border-t border-border pt-4 text-sm">
              <summary className="w-fit cursor-pointer rounded-sm font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                Recorded data
              </summary>
              <pre className="mt-3 whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-text">
                {JSON.stringify(log.edited_json, null, 2)}
              </pre>
            </details>
          ) : null}
        </div>
      </td>
    </tr>
  );
}
