import type { ArchivedExperiment } from '../archiveTypes';
import { archiveMetrics } from '../utils/archiveMetrics';

const AXIS_MAX = 2;
const ticks = [0, 1, 2];
const series = [
  { label: 'Base MAE', className: 'bg-text-muted' },
  { label: 'Fine-tuned MAE', className: 'bg-primary' },
] as const;
const columns =
  'grid grid-cols-[minmax(0,1fr)_3rem] gap-x-3 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_3rem]';

export function ArchiveSlmComparisonChart({ experiment }: { experiment: ArchivedExperiment }) {
  const rows = experiment.runs.flatMap((run) => {
    const metrics = archiveMetrics(experiment, run.criteria);
    if (metrics.baseMae == null || metrics.adapterMae == null) return [];
    return [{ run, values: [metrics.baseMae, metrics.adapterMae] }];
  });
  if (!rows.length) return null;

  return (
    <figure aria-labelledby="slm-comparison-heading" className="space-y-4">
      <figcaption className="space-y-1">
        <h3 id="slm-comparison-heading" className="text-base font-semibold text-text">
          MAE by SLM
        </h3>
        <p className="text-xs leading-relaxed text-text-muted">
          Base and fine-tuned scoring error on the same 0–2 scale. Lower is better.
        </p>
      </figcaption>
      <div className="min-w-0">
        {rows.map(({ run, values }) => (
          <div
            key={run.adapter_validation_id}
            role="group"
            aria-label={run.title}
            className={`${columns} items-center border-b border-border/60 py-2 sm:py-0`}
          >
            <span className="col-span-2 text-xs leading-relaxed text-text-muted sm:col-span-1 sm:pr-1 sm:text-right [overflow-wrap:anywhere]">
              {run.title}
            </span>
            <div aria-hidden="true" className="relative flex min-w-0 flex-col gap-1 py-3">
              {ticks.map((tick) => (
                <span
                  key={tick}
                  className="pointer-events-none absolute inset-y-0 border-l border-dashed border-border/60"
                  style={{ left: `${(tick / AXIS_MAX) * 100}%` }}
                />
              ))}
              {values.map((value, index) => (
                <span
                  key={series[index].label}
                  className={`relative h-5 rounded-sm ${series[index].className}`}
                  style={{
                    width: `${(Math.min(value, AXIS_MAX) / AXIS_MAX) * 100}%`,
                  }}
                />
              ))}
            </div>
            <div className="space-y-1 py-3 text-right text-xs leading-5 tabular-nums text-text">
              {values.map((value, index) => (
                <p key={series[index].label}>
                  <span className="sr-only">{series[index].label}: </span>
                  {value.toFixed(3)}
                </p>
              ))}
            </div>
          </div>
        ))}
        <div aria-hidden="true" className={columns}>
          <div className="relative h-5 text-xs tabular-nums text-text-muted sm:col-start-2">
            {ticks.map((tick) => (
              <span
                key={tick}
                className="absolute -translate-x-1/2"
                style={{ left: `${(tick / AXIS_MAX) * 100}%` }}
              >
                {tick}
              </span>
            ))}
          </div>
        </div>
      </div>
      {rows.some((row) => row.values.some((value) => value > AXIS_MAX)) ? (
        <p className="text-xs text-text-muted">
          Bars above 2 stop at the axis limit; exact values are shown on the right.
        </p>
      ) : null}
      <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs text-text">
        {series.map((item) => (
          <span key={item.label} className="inline-flex items-center gap-2">
            <span aria-hidden="true" className={`size-2.5 rounded-xs ${item.className}`} />
            {item.label}
          </span>
        ))}
      </div>
    </figure>
  );
}
