import type { ArchivedExperiment } from '../archiveTypes';
import { archiveMetrics } from '../utils/archiveMetrics';

export function ExperimentOverview({ experiment }: { experiment: ArchivedExperiment }) {
  const metrics = archiveMetrics(experiment);
  const criteria = experiment.runs.flatMap((run) => run.criteria);
  const audited = criteria.filter(
    (c) =>
      ['ok', 'repaired'].includes(c.base.status) &&
      ['ok', 'repaired'].includes(c.adapter.status) &&
      typeof c.base.quote_exact_in_claimed_chunk === 'boolean' &&
      typeof c.adapter.quote_exact_in_claimed_chunk === 'boolean',
  );
  const baseGrounded = audited.filter((c) => c.base.quote_exact_in_claimed_chunk).length;
  const tunedGrounded = audited.filter((c) => c.adapter.quote_exact_in_claimed_chunk).length;
  const format = (value: number | null) => (value == null ? 'Unavailable' : value.toFixed(3));
  const difference =
    metrics.baseMae != null && metrics.adapterMae != null
      ? metrics.adapterMae - metrics.baseMae
      : null;
  return (
    <section aria-label="Evaluation overview" className="border-y border-border bg-surface">
      <p className="border-b border-border px-4 py-2 text-xs text-text-muted">
        Base → fine-tuned model · Matching synthetic references · No combined quality score
      </p>
      <div className="grid divide-y divide-border lg:grid-cols-3 lg:divide-x lg:divide-y-0">
        <section aria-label="Scoring accuracy results" className="space-y-3 p-4 sm:p-5">
          <h3 className="text-base font-semibold text-text">Scoring accuracy</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex flex-wrap justify-between gap-x-3 gap-y-1">
              <dt className="text-text-muted">MAE · lower is better</dt>
              <dd className="font-semibold tabular-nums text-text">
                {format(metrics.baseMae)} → {format(metrics.adapterMae)}
              </dd>
            </div>
            <div className="flex flex-wrap justify-between gap-x-3 gap-y-1">
              <dt className="text-text-muted">Exact matches</dt>
              <dd className="font-semibold tabular-nums text-text">
                {metrics.baseExact}/{metrics.count} → {metrics.adapterExact}/{metrics.count}
              </dd>
            </div>
          </dl>
          <p className="text-xs font-medium text-text">
            {difference == null
              ? 'Scoring comparison unavailable'
              : difference < 0
                ? 'Lower observed scoring error'
                : difference > 0
                  ? 'Higher observed scoring error'
                  : 'No overall change in scoring error'}
          </p>
          <p className="text-xs leading-relaxed text-text-muted">
            {metrics.count} comparable criterion scores.
            {experiment.primary_criteria
              ? ` Scoring scope: ${experiment.primary_criteria.join(', ')} only.`
              : ' All archived criteria included.'}
          </p>
        </section>
        <section aria-label="Evidence quality results" className="space-y-3 p-4 sm:p-5">
          <h3 className="text-base font-semibold text-text">Evidence quality</h3>
          {audited.length ? (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-text-muted">Exact quotation grounding</h4>
              <p className="flex flex-wrap gap-x-2 text-lg font-semibold tabular-nums text-text">
                <span>{((baseGrounded / audited.length) * 100).toFixed(1)}%</span>
                <span aria-hidden="true">→</span>
                <span>{((tunedGrounded / audited.length) * 100).toFixed(1)}%</span>
              </p>
              <p className="text-xs text-text-muted">
                {baseGrounded}/{audited.length} → {tunedGrounded}/{audited.length} exact source
                quotations
              </p>
              <p className="text-xs leading-relaxed text-text-muted">
                Verbatim occurrence in the cited source chunk; {audited.length} of {criteria.length}{' '}
                comparisons audited.
              </p>
            </div>
          ) : (
            <p className="text-sm text-text-muted">Quotation grounding not audited.</p>
          )}
          <div className="border-t border-border pt-3">
            <p className="text-xs font-medium text-text">Evidence relevance</p>
            <p className="mt-1 text-sm text-text-muted">Not yet formally assessed</p>
            <p className="mt-2 text-xs leading-relaxed text-text-muted">
              An exact quotation does not establish that it supports the assigned score.
            </p>
          </div>
        </section>
        <section aria-label="Reasoning quality results" className="space-y-3 p-4 sm:p-5">
          <h3 className="text-base font-semibold text-text">Reasoning quality</h3>
          <p className="text-sm text-text-muted">Not yet formally assessed</p>
          <p className="text-xs leading-relaxed text-text-muted">
            Rubric consistency requires a structured review of whether each explanation supports its
            assigned level.
          </p>
          <p className="border-t border-border pt-3 text-xs leading-relaxed text-text-muted">
            Inspect captured explanations under Evidence &amp; reasoning. Stored fallback
            justifications remain separate from model reasoning.
          </p>
        </section>
      </div>
    </section>
  );
}
