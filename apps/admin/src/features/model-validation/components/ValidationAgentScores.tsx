import { ShieldWarning } from '@phosphor-icons/react';
import { cn } from '@equiped/ui';
import type { ModelValidationCriterionScore } from '../types';

type ValidationAgentScoresProps = {
  agentName: string;
  displayRubricVersion?: number | null;
  criteria: ModelValidationCriterionScore[];
  isAgentSkipped: boolean;
  isTerminal: boolean;
};

export function ValidationAgentScores({
  agentName,
  displayRubricVersion,
  criteria,
  isAgentSkipped,
  isTerminal,
}: ValidationAgentScoresProps) {
  return (
    <article className="overflow-hidden rounded-sm border border-border bg-surface">
      <header className="flex items-center justify-between gap-2 border-b border-border bg-surface-subtle px-3.5 py-2.5">
        <div className="flex items-center gap-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-text">{agentName}</h4>
          {displayRubricVersion ? (
            <span className="rounded-xs bg-surface border border-border px-1.5 py-0.2 text-[10px] font-mono font-semibold text-text-muted tabular-nums">
              Rubric v{displayRubricVersion}
            </span>
          ) : null}
        </div>
        {isAgentSkipped ? (
          <span className="inline-flex items-center gap-1 rounded-xs bg-surface px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-text-muted border border-border">
            <ShieldWarning className="size-3 text-warning" aria-hidden="true" />
            Skipped — no curriculum
          </span>
        ) : null}
      </header>
      {isAgentSkipped ? (
        <p className="px-4 py-3 text-xs font-medium leading-relaxed text-text-muted">
          Coordinator scoring was skipped for this run. No expected, actual, or error values are
          reported.
        </p>
      ) : (
        <table className="w-full border-collapse text-left text-xs">
          <thead className="bg-surface text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border">
            <tr>
              <th className="px-3 py-2">Criterion</th>
              <th className="px-3 py-2 text-right">Expected</th>
              <th className="px-3 py-2 text-right">Actual</th>
              <th className="px-3 py-2 text-right">Error</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {criteria.map((score) => {
              const expected = score.expected_score;
              const actual = score.actual_score;
              const error = score.absolute_error;
              const actualLabel =
                actual == null ? (isTerminal ? 'Unavailable' : 'Pending') : String(actual);
              const errorLabel =
                error == null ? (isTerminal ? 'Unavailable' : 'Pending') : error.toFixed(2);
              const isExactMatch = error === 0;

              return (
                <tr
                  key={score.expected_score_id}
                  className="hover:bg-surface-subtle/50 transition-colors"
                >
                  <th scope="row" className="px-3 py-2.5 font-semibold text-text">
                    <span className="block break-words">
                      {score.criterion_id} · {score.criterion_title}
                    </span>
                  </th>
                  <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums text-text">
                    {expected}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums text-text">
                    {actual == null ? (
                      <span
                        className={cn(
                          'inline-block rounded-xs px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider',
                          isTerminal
                            ? 'bg-destructive-soft text-destructive border border-destructive/20'
                            : 'bg-surface-subtle text-text-muted border border-border',
                        )}
                      >
                        {actualLabel}
                      </span>
                    ) : (
                      actualLabel
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums whitespace-nowrap">
                    {error == null ? (
                      <span
                        className={cn(
                          'inline-block rounded-xs px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider',
                          isTerminal
                            ? 'bg-destructive-soft text-destructive border border-destructive/20'
                            : 'bg-surface-subtle text-text-muted border border-border',
                        )}
                      >
                        {errorLabel}
                      </span>
                    ) : (
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 font-mono font-bold text-xs',
                          isExactMatch ? 'text-success' : 'text-warning',
                        )}
                      >
                        <span>{errorLabel}</span>
                        <span className="text-[10px] font-bold">{isExactMatch ? '✓' : '⚠'}</span>
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
            {criteria.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  className="px-3 py-3 text-center text-xs font-medium text-text-muted"
                >
                  No criteria recorded for this agent.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      )}
    </article>
  );
}
