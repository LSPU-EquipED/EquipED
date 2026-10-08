import type { CoordinatorAlignmentAdvisory } from '@equiped/types';

/** Separate evidence review: intentionally does not accept or compute official totals. */
export function CurriculumAlignmentSupplement({
  advisory,
}: {
  advisory: CoordinatorAlignmentAdvisory;
}) {
  return (
    <section aria-label="Advisory curriculum alignment" className="rounded-md border border-border bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-text">C-01 · Curriculum Alignment</h3>
        <span className="text-sm font-semibold tabular-nums text-text">{advisory.score} / 4</span>
      </div>
      <p className="mt-1 text-xs text-text-muted">
        Advisory only. Excluded from the official subtotal, matrix composite, and institutional PDF.
      </p>
      <p className="mt-3 text-sm text-text">{advisory.justification}</p>
      <details className="mt-3 border-t border-border pt-2">
        <summary className="cursor-pointer text-xs font-medium text-text-muted focus-visible:outline-2 focus-visible:outline-ring">
          Objective evidence ({advisory.objective_matches.length})
        </summary>
        <ul className="mt-3 space-y-3">
          {advisory.objective_matches.map((row) => (
            <li key={row.objective_id} className="text-sm text-text">
              <p className="mb-1 text-xs font-medium text-text-muted">{row.objective_id}</p>
              <p className="whitespace-pre-wrap break-words">{row.objective_text}</p>
              <p className="mt-1 text-xs font-medium text-text-muted">
                {row.matched ? 'Matched to curriculum' : 'Not matched to curriculum'}
                {row.rejected ? ' · Unsupported claim rejected' : ''}
              </p>
              {row.matched && (
                <blockquote className="mt-2 border-l-2 border-border pl-3 text-xs whitespace-pre-wrap break-words text-text-muted">
                  {row.excerpt}
                </blockquote>
              )}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
