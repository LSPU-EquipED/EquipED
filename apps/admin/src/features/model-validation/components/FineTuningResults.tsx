import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CaretDown, DownloadSimple } from '@phosphor-icons/react';
import { Button, cn, TABLE_STYLES } from '@equiped/ui';
import { modelValidationApi } from '../api/modelValidation.api';
import type { ArchivedExperiment, FineTuningArchive } from '../archiveTypes';
import { archiveMetrics } from '../utils/archiveMetrics';
import { ArchivedEvidence } from './ArchivedEvidence';
import { ExperimentOverview } from './ExperimentOverview';
import { ArchiveComparisonBars } from './ArchiveComparisonBars';
import { ArchiveSlmComparisonChart } from './ArchiveSlmComparisonChart';
import { ArchiveMethodology } from './ArchiveMethodology';

const sections = ['Comparisons', 'Evidence & reasoning', 'Training', 'Method'] as const;
type Section = (typeof sections)[number];
const format = (value: number | null) => (value == null ? 'Unavailable' : value.toFixed(2));

function downloadArchive(archive: FineTuningArchive, experiment: ArchivedExperiment) {
  const content = {
    schema_version: archive.schema_version,
    archived_on: archive.archived_on,
    experiment,
  };
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(content, null, 2)], { type: 'application/json' }),
  );
  const link = document.createElement('a');
  link.href = url;
  link.download = `equiped-${experiment.adapter_label}-results.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Scores({ experiment }: { experiment: ArchivedExperiment }) {
  const metrics = archiveMetrics(experiment);
  return (
    <div className="space-y-5">
      <ArchiveSlmComparisonChart experiment={experiment} />
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs">
        <span>
          <strong className="text-success">{metrics.closer}</strong> closer
        </span>
        <span>
          <strong>{metrics.unchanged}</strong> unchanged error
        </span>
        <span>
          <strong className="text-destructive">{metrics.farther}</strong> farther
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className={TABLE_STYLES.table} aria-label="Archived results by SLM">
          <thead>
            <tr>
              {['SLM comparison', 'Base MAE', 'Fine-tuned MAE', 'Exact matches', 'Outcome'].map(
                (h) => (
                  <th key={h} scope="col" className={TABLE_STYLES.th}>
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {experiment.runs.map((run) => {
              const m = archiveMetrics(experiment, run.criteria);
              const delta =
                m.baseMae != null && m.adapterMae != null ? m.adapterMae - m.baseMae : null;
              return (
                <tr key={run.adapter_validation_id} className="border-t border-border">
                  <th scope="row" className={cn(TABLE_STYLES.td, 'font-medium text-text')}>
                    {run.title}
                  </th>
                  <td className={cn(TABLE_STYLES.td, 'tabular-nums')}>{format(m.baseMae)}</td>
                  <td className={cn(TABLE_STYLES.td, 'tabular-nums')}>{format(m.adapterMae)}</td>
                  <td className={cn(TABLE_STYLES.td, 'whitespace-nowrap tabular-nums')}>
                    {m.baseExact}/{m.count} → {m.adapterExact}/{m.count}
                  </td>
                  <td
                    className={cn(
                      TABLE_STYLES.td,
                      'font-medium',
                      delta != null && delta < 0
                        ? 'text-success'
                        : delta != null && delta > 0
                          ? 'text-destructive'
                          : 'text-text-muted',
                    )}
                  >
                    {delta == null
                      ? 'Unavailable'
                      : delta < 0
                        ? 'Improved'
                        : delta > 0
                          ? 'Worsened'
                          : 'Unchanged'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs leading-relaxed text-text-muted">
        Metrics use matching references and exclude fallback or unavailable responses. Repaired
        responses are included and identified under Evidence & reasoning.{' '}
        {experiment.primary_criteria
          ? `Only ${experiment.primary_criteria.join(', ')} contributes to these metrics; other criteria are stability controls.`
          : 'These are historical synthetic-reference results, not expert-accuracy estimates.'}
      </p>
    </div>
  );
}

function Training({ experiment }: { experiment: ArchivedExperiment }) {
  const t = experiment.training;
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-text">Training-objective progress</h3>
      <p className="max-w-prose text-sm leading-relaxed text-text-muted">
        These measurements show preference optimization on logged training batches. They do not
        measure generated scoring accuracy or unseen-document performance.
      </p>
      {t ? (
        <>
          <p className="text-sm text-text">
            <strong>{t.steps}</strong> optimizer steps · <strong>{t.epochs}</strong> epochs
          </p>
          <div className="grid gap-6 sm:grid-cols-2">
            {[
              {
                label: 'DPO loss',
                first: t.first_loss,
                last: t.last_loss,
                direction: 'Lower is better',
              },
              {
                label: 'Preference reward margin',
                first: t.first_margin,
                last: t.last_margin,
                direction: 'Higher is better',
              },
            ].map((metric) => (
              <section key={metric.label} className="space-y-3">
                <div>
                  <h4 className="text-sm font-semibold text-text">{metric.label}</h4>
                  <p className="text-xs text-text-muted">{metric.direction}</p>
                </div>
                <ArchiveComparisonBars
                  label={`${metric.label} comparison`}
                  rows={[
                    {
                      label: 'First logged step',
                      value: metric.first,
                      display: metric.first.toFixed(6),
                    },
                    {
                      label: 'Last logged step',
                      value: metric.last,
                      display: metric.last.toFixed(6),
                    },
                  ]}
                />
              </section>
            ))}
          </div>
          <table className={TABLE_STYLES.table} aria-label="Archived training metrics">
            <thead>
              <tr>
                {['Training measure', 'First logged step', 'Last logged step'].map((h) => (
                  <th key={h} className={TABLE_STYLES.th} scope="col">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['DPO loss', t.first_loss, t.last_loss],
                ['Preference reward margin', t.first_margin, t.last_margin],
              ].map(([name, first, last]) => (
                <tr key={name} className="border-t border-border">
                  <th scope="row" className={TABLE_STYLES.td}>
                    {name}
                  </th>
                  <td className={cn(TABLE_STYLES.td, 'tabular-nums')}>
                    {Number(first).toFixed(6)}
                  </td>
                  <td className={cn(TABLE_STYLES.td, 'tabular-nums')}>{Number(last).toFixed(6)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-text-muted">
            First and last logged measurements only. No intermediate learning curve was archived.
          </p>
        </>
      ) : (
        <p className="rounded-sm bg-surface-subtle p-4 text-sm text-text">
          Training metrics were not captured for this fine-tuned model. No learning curve has been
          reconstructed.
        </p>
      )}
    </div>
  );
}

export function FineTuningResults() {
  const query = useQuery({
    queryKey: ['admin', 'fine-tuning-archive'],
    queryFn: modelValidationApi.getFineTuningArchive,
    staleTime: Infinity,
    retry: false,
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [section, setSection] = useState<Section>('Comparisons');
  const archive = query.data;
  const experiments = archive?.experiments ?? [];
  const experiment = experiments.find((e) => e.id === selected) ?? experiments[0];
  const availableSections = sections.filter((view) => {
    if (view === 'Training') return Boolean(experiment?.training);
    if (view === 'Comparisons') return Boolean(experiment && archiveMetrics(experiment).count);
    if (view === 'Evidence & reasoning') {
      return experiment?.runs.some((run) => run.criteria.length);
    }
    return true;
  });
  const activeSection = availableSections.includes(section) ? section : availableSections[0];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-text">Fine-Tuning Results</h2>
          <p className="mt-1 text-sm text-text-muted">
            Explore measured results across the archived experiments.
          </p>
        </div>
        <span className="rounded-sm border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text-muted">
          Archived snapshots · Read only
        </span>
      </header>
      {query.isLoading ? (
        <div
          role="status"
          aria-label="Loading archived experiments"
          className="space-y-4 motion-safe:animate-pulse"
        >
          <div className="h-10 max-w-lg rounded-sm bg-surface-subtle" />
          <div className="h-40 border-y border-border bg-surface-subtle" />
          <span className="sr-only">Loading archived experiments…</span>
        </div>
      ) : query.isError ? (
        <div role="alert" className="space-y-3 rounded-sm border border-border p-4">
          <p className="text-sm text-text">Unable to load the experiment archive.</p>
          <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
            Try again
          </Button>
        </div>
      ) : !archive || !experiment ? (
        <p className="text-sm text-text-muted">No archived experiments are available.</p>
      ) : (
        <article className="min-w-0 space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <label className="w-full min-w-0 space-y-2 text-xs font-semibold text-text sm:max-w-lg">
              Experiment
              <select
                id="fine-tuning-experiment"
                value={experiment.id}
                onChange={(event) => {
                  setSelected(event.target.value);
                  setSection('Comparisons');
                }}
                className="block min-h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-normal text-text focus-visible:outline-2 focus-visible:outline-ring"
              >
                {experiments.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => downloadArchive(archive, experiment)}
            >
              <DownloadSimple size={16} aria-hidden="true" />
              Export results
            </Button>
          </div>
          <p className="text-xs text-text-muted">
            {experiment.scope} · {experiment.runs.length} comparisons
            {experiment.pair_count == null
              ? ''
              : ` · ${experiment.pair_count} exported training pairs`}
          </p>
          <ExperimentOverview experiment={experiment} />
          <details key={experiment.id} className="group rounded-sm border border-border bg-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-sm px-4 py-3 text-sm font-semibold text-text focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
              <span>Experiment details</span>
              <CaretDown
                className="size-4 transition-transform duration-150 group-open:rotate-180 motion-reduce:transition-none"
                aria-hidden="true"
              />
            </summary>
            <div className="min-w-0 space-y-5 border-t border-border p-4">
              <div
                aria-label="Experiment views"
                className="flex gap-1 overflow-x-auto border-b border-border"
              >
                {availableSections.map((view) => (
                  <button
                    key={view}
                    type="button"
                    aria-pressed={activeSection === view}
                    onClick={() => setSection(view)}
                    className={cn(
                      'min-h-10 shrink-0 cursor-pointer border-b-2 px-3 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-ring',
                      activeSection === view
                        ? 'border-primary text-primary'
                        : 'border-transparent text-text-muted hover:text-text',
                    )}
                  >
                    {view}
                  </button>
                ))}
              </div>
              <div className="min-w-0">
                {activeSection === 'Comparisons' ? (
                  <Scores experiment={experiment} />
                ) : activeSection === 'Evidence & reasoning' ? (
                  <ArchivedEvidence key={experiment.id} experiment={experiment} />
                ) : activeSection === 'Training' ? (
                  <Training experiment={experiment} />
                ) : (
                  <ArchiveMethodology experiment={experiment} archivedOn={archive.archived_on} />
                )}
              </div>
            </div>
          </details>
        </article>
      )}
    </div>
  );
}
