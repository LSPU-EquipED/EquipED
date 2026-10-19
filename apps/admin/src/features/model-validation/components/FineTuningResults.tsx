import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DownloadSimple } from '@phosphor-icons/react';
import { Button, cn, TABLE_STYLES } from '@equiped/ui';
import { modelValidationApi } from '../api/modelValidation.api';
import type { ArchivedExperiment, FineTuningArchive } from '../archiveTypes';
import { archiveMetrics } from '../utils/archiveMetrics';
import { experimentResultSummary, fineTunedModelLabel } from '../utils/archivePresentation';
import { ArchivedEvidence } from './ArchivedEvidence';
import { ExperimentOverview } from './ExperimentOverview';

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

function Method({
  experiment,
  archivedOn,
}: {
  experiment: ArchivedExperiment;
  archivedOn: string;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="mb-2 text-base font-semibold text-text">Dataset and references</h3>
        <p className="text-sm text-text">{experiment.dataset_note}</p>
        <p className="mt-2 text-sm text-text-muted">{experiment.reference_kind}</p>
      </div>
      <section aria-label="Experiment conditions" className="space-y-2">
        <h3 className="text-base font-semibold text-text">Experiment conditions</h3>
        <ul className="list-disc space-y-1.5 pl-4 text-sm leading-relaxed text-text-muted">
          {experiment.limitations.map((note) => (
            <li key={note}>
              {note
                .replace(/\badapters\b/gi, 'fine-tuned models')
                .replace(/\badapter\b/gi, 'fine-tuned model')}
            </li>
          ))}
        </ul>
        <p className="pt-2 text-xs text-text-muted">
          Archived on {archivedOn}. Results remain available independently of live validation
          records or loaded models.
        </p>
      </section>
      <p className="text-sm leading-relaxed text-text">
        Each comparison preserves the original validation identifiers and exact stored criterion
        evidence and reasoning. Both initial prompt envelopes were verified identical within each
        pair. Prompt hashes are retained below; complete PDFs and prompts are not included in this
        curated archive.
      </p>
      {experiment.runs.map((run) => (
        <details key={run.adapter_validation_id} className="rounded-sm border border-border">
          <summary className="cursor-pointer p-3 text-sm font-semibold text-primary focus-visible:outline-2 focus-visible:outline-ring">
            {run.title} · Run provenance
          </summary>
          <dl className="grid gap-2 px-3 pb-3 text-xs [overflow-wrap:anywhere]">
            <dt className="font-semibold">Base validation</dt>
            <dd>{run.base_validation_id}</dd>
            <dt className="font-semibold">
              {fineTunedModelLabel(experiment.adapter_label)} validation
            </dt>
            <dd>{run.adapter_validation_id}</dd>
            {run.prompt_hashes.map((hash) => (
              <div key={hash.sha256}>
                <dt className="font-semibold">Identical prompt · {hash.criteria.join(', ')}</dt>
                <dd className="mt-1 font-mono">{hash.sha256}</dd>
              </div>
            ))}
          </dl>
        </details>
      ))}
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
  const [agent, setAgent] = useState('sme');
  const [selected, setSelected] = useState('v7');
  const [section, setSection] = useState<Section>('Comparisons');
  const archive = query.data;
  const experiments =
    archive?.experiments.filter((e) => e.adapter_label.split('-')[0] === agent) ?? [];
  const experiment = experiments.find((e) => e.id === selected) ?? experiments[0];
  const agentLabel = agent === 'coordinator' ? 'Coordinator' : agent.toUpperCase();
  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-text">Fine-Tuning Results</h2>
          <p className="mt-1 text-sm text-text-muted">
            Compare scoring accuracy, source evidence, and rubric reasoning by agent.
          </p>
        </div>
        <span className="rounded-sm border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text-muted">
          Archived snapshots · Read only
        </span>
      </header>
      {query.isLoading ? (
        <p role="status" className="text-sm text-text-muted">
          Loading archived experiments…
        </p>
      ) : query.isError ? (
        <div role="alert" className="space-y-3 rounded-sm border border-border p-4">
          <p className="text-sm text-text">Unable to load the experiment archive.</p>
          <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
            Try again
          </Button>
        </div>
      ) : !archive || !archive.experiments.length ? (
        <p className="text-sm text-text-muted">No archived experiments are available.</p>
      ) : (
        <div className="min-w-0 space-y-6">
          <div
            role="group"
            aria-label="Agent"
            className="grid grid-cols-2 gap-1 border-b border-border pb-3 sm:flex sm:flex-wrap"
          >
            {['sme', 'gad', 'coordinator', 'itso'].map((value) => {
              const label = value === 'coordinator' ? 'Coordinator' : value.toUpperCase();
              const count = archive.experiments.filter(
                (e) => e.adapter_label.split('-')[0] === value,
              ).length;
              return (
                <button
                  key={value}
                  type="button"
                  aria-label={label}
                  aria-pressed={agent === value}
                  onClick={() => {
                    setAgent(value);
                    setSection('Comparisons');
                  }}
                  className={cn(
                    'min-h-10 cursor-pointer rounded-sm px-4 py-2 text-sm font-semibold transition-colors motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-ring',
                    agent === value
                      ? 'bg-primary text-primary-foreground'
                      : 'text-text-muted hover:bg-surface-subtle hover:text-text',
                  )}
                >
                  {label}
                  <span aria-hidden="true" className="ml-2 font-normal tabular-nums">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
          {!experiment ? (
            <section role="status" className="border-y border-border py-10 text-center">
              <h3 className="text-lg font-semibold text-text">
                No {agentLabel} experiments archived yet
              </h3>
              <p className="mx-auto mt-2 max-w-prose text-sm leading-relaxed text-text-muted">
                Scoring accuracy, evidence quality, and reasoning quality will appear here when
                reviewed results are archived. No measurements are available yet.
              </p>
            </section>
          ) : (
            <>
              <div className="flex flex-wrap items-end justify-between gap-3">
                <label className="min-w-0 w-full space-y-2 text-xs font-semibold text-text sm:max-w-lg">
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
                        {fineTunedModelLabel(e.adapter_label)} — {e.title}
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
                {experiment.adapter_label.split('-')[0].toUpperCase()} · {experiment.scope} ·{' '}
                {experiment.runs.length} comparisons
                {experiment.pair_count == null
                  ? ''
                  : ` · ${experiment.pair_count} exported training pairs`}
              </p>
              <article className="min-w-0 space-y-6">
                <header className="space-y-2 border-l border-primary pl-4">
                  <h3 className="text-lg font-semibold text-primary">Result summary</h3>
                  <p className="max-w-4xl text-sm leading-relaxed text-text">
                    {experimentResultSummary(experiment)
                      .split(/(\b\d+(?:\.\d+)?\b)/g)
                      .map((part, index) =>
                        index % 2 === 1 ? (
                          <strong key={index} className="font-semibold tabular-nums">
                            {part}
                          </strong>
                        ) : (
                          part
                        ),
                      )}
                  </p>
                </header>
                <ExperimentOverview experiment={experiment} />
                <div
                  aria-label="Experiment views"
                  className="flex gap-1 overflow-x-auto border-b border-border"
                >
                  {sections.map((s) => (
                    <button
                      key={s}
                      type="button"
                      aria-pressed={section === s}
                      onClick={() => setSection(s)}
                      className={cn(
                        'min-h-10 shrink-0 cursor-pointer border-b-2 px-3 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-ring',
                        section === s
                          ? 'border-primary text-primary'
                          : 'border-transparent text-text-muted hover:text-text',
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                <div className="min-w-0">
                  {section === 'Comparisons' ? (
                    <Scores experiment={experiment} />
                  ) : section === 'Evidence & reasoning' ? (
                    <ArchivedEvidence key={experiment.id} experiment={experiment} />
                  ) : section === 'Training' ? (
                    <Training experiment={experiment} />
                  ) : (
                    <Method experiment={experiment} archivedOn={archive.archived_on} />
                  )}
                </div>
              </article>
            </>
          )}
        </div>
      )}
    </div>
  );
}
