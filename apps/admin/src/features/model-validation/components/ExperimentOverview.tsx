import type { ArchivedExperiment } from '../archiveTypes';
import { archiveMetrics } from '../utils/archiveMetrics';
import { ArchiveComparisonBars } from './ArchiveComparisonBars';

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
  if (!metrics.count && !audited.length) return null;
  return (
    <section aria-label="Evaluation overview" className="@container/archive-overview space-y-3">
      <div
        className={`grid gap-5 ${metrics.count && audited.length ? '@min-[52rem]/archive-overview:grid-cols-2' : ''}`}
      >
        {metrics.count > 0 ? (
          <section
            aria-label="Scoring accuracy results"
            className="min-w-0 rounded-md border border-border bg-surface p-4 sm:p-5"
          >
            <div className="mb-5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 className="text-base font-semibold text-text">Scoring accuracy</h3>
              <span className="text-xs text-text-muted">Lower is better</span>
              <p className="w-full text-xs text-text-muted">
                Mean absolute error · Matching synthetic references
              </p>
            </div>
            <div
              className={`grid gap-5 ${!audited.length ? '@min-[40rem]/archive-overview:grid-cols-[minmax(0,1fr)_minmax(12rem,0.5fr)]' : ''}`}
            >
              {metrics.baseMae != null && metrics.adapterMae != null ? (
                <ArchiveComparisonBars
                  label="Mean absolute error comparison"
                  domain={[0, 3]}
                  rows={[
                    { label: 'Base', value: metrics.baseMae, display: format(metrics.baseMae) },
                    {
                      label: 'Fine-tuned model',
                      value: metrics.adapterMae,
                      display: format(metrics.adapterMae),
                    },
                  ]}
                />
              ) : null}
              <div
                className={`space-y-3 border-t border-border pt-4 ${!audited.length ? '@min-[40rem]/archive-overview:border-l @min-[40rem]/archive-overview:border-t-0 @min-[40rem]/archive-overview:pl-5 @min-[40rem]/archive-overview:pt-0' : ''}`}
              >
                <dl className="space-y-2 text-sm">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <dt className="text-text-muted">Exact matches</dt>
                    <dd className="font-semibold tabular-nums text-text">
                      {metrics.baseExact}/{metrics.count} → {metrics.adapterExact}/{metrics.count}
                    </dd>
                  </div>
                </dl>
                <p className="text-sm font-medium leading-relaxed text-text">
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
              </div>
            </div>
          </section>
        ) : null}
        {audited.length > 0 ? (
          <section
            aria-label="Evidence quality results"
            className="min-w-0 space-y-4 rounded-md border border-border bg-surface p-4 sm:p-5"
          >
            <div>
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h3 className="text-base font-semibold text-text">Evidence quality</h3>
                <span className="text-xs text-text-muted">Higher is better</span>
              </div>
              <h4 className="mt-1 text-xs font-normal text-text-muted">
                Exact quotation grounding
              </h4>
            </div>
            <div className="space-y-4">
              <ArchiveComparisonBars
                label="Exact quotation grounding comparison"
                domain={[0, 100]}
                unit="%"
                rows={[
                  {
                    label: 'Base',
                    value: (baseGrounded / audited.length) * 100,
                    display: `${((baseGrounded / audited.length) * 100).toFixed(1)}%`,
                  },
                  {
                    label: 'Fine-tuned model',
                    value: (tunedGrounded / audited.length) * 100,
                    display: `${((tunedGrounded / audited.length) * 100).toFixed(1)}%`,
                  },
                ]}
              />
              <p className="text-xs text-text-muted">
                {baseGrounded}/{audited.length} → {tunedGrounded}/{audited.length} exact source
                quotations
              </p>
              <p className="text-xs leading-relaxed text-text-muted">
                Verbatim occurrence in the cited source chunk; {audited.length} of {criteria.length}{' '}
                comparisons audited.
              </p>
            </div>
            <p className="border-t border-border pt-3 text-xs leading-relaxed text-text-muted">
              An exact quotation does not establish that it supports the assigned score.
            </p>
          </section>
        ) : null}
      </div>
    </section>
  );
}
