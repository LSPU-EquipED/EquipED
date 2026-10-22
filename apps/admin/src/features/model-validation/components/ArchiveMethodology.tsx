import { CaretDown } from '@phosphor-icons/react';
import type { ArchivedExperiment } from '../archiveTypes';
import { presentArchiveLimitation } from '../utils/archiveMethodology';
import { FINE_TUNED_MODEL_LABEL } from '../utils/archivePresentation';

export function ArchiveMethodology({
  experiment,
  archivedOn,
}: {
  experiment: ArchivedExperiment;
  archivedOn: string;
}) {
  const facts = [
    ['Comparisons', experiment.runs.length],
    ['Unique SLMs', experiment.unique_slm_count ?? 'Not recorded'],
    ['Dataset pairs', experiment.pair_count ?? 'Not recorded'],
    [
      'Reference scores',
      /synthetic/i.test(experiment.reference_kind) ? 'Synthetic' : experiment.reference_kind,
    ],
  ];

  return (
    <section aria-label="Methodology" className="space-y-5">
      <h3 className="text-base font-semibold text-text">Methodology</h3>
      <div className="grid gap-7 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-8">
        <section
          aria-label="Dataset facts"
          className="min-w-0 space-y-4 lg:border-r lg:border-border lg:pr-8"
        >
          <h4 className="text-sm font-semibold text-text">Dataset</h4>
          <dl className="grid grid-cols-2 gap-x-5 border-t border-border">
            {facts.map(([label, value]) => (
              <div key={label} className="min-w-0 border-b border-border py-3">
                <dt className="text-xs font-medium text-text-muted">{label}</dt>
                <dd className="mt-1 text-base font-semibold tabular-nums text-text [overflow-wrap:anywhere]">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          {experiment.dataset_note !== 'Dataset pair count was not captured in this archive.' ? (
            <p className="max-w-[70ch] text-sm leading-relaxed text-text">
              {experiment.dataset_note}
            </p>
          ) : null}
          <p className="max-w-[70ch] text-sm leading-relaxed text-text">
            {experiment.reference_kind}
          </p>
        </section>
        <section aria-label="Study limitations" className="min-w-0 space-y-4">
          <h4 className="text-sm font-semibold text-text">Limitations</h4>
          <ul className="max-w-[70ch] space-y-3.5 text-sm leading-relaxed text-text">
            {experiment.limitations.map((note) => {
              const item = presentArchiveLimitation(note);
              return (
                <li key={note}>
                  <strong className="font-semibold">{item.label}: </strong>
                  {item.text}
                </li>
              );
            })}
          </ul>
        </section>
      </div>
      <details key={experiment.id} className="group/provenance border-t border-border">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 py-3 text-sm font-semibold text-text focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
          <span>Provenance</span>
          <CaretDown
            aria-hidden="true"
            className="size-4 transition-transform duration-150 group-open/provenance:rotate-180 motion-reduce:transition-none"
          />
        </summary>
        <div className="space-y-5 pb-3">
          <dl className="text-sm text-text">
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              <dt className="font-semibold">Archived on</dt>
              <dd>{archivedOn}</dd>
            </div>
          </dl>
          <p className="max-w-[70ch] text-sm leading-relaxed text-text">
            Original comparison identifiers and available prompt hashes are listed below. Captured
            evidence and reasoning remain in Evidence &amp; reasoning. These snapshots remain
            available independently of live validation records or loaded models. Complete PDFs and
            prompts are outside this archive.
          </p>
          <div className="divide-y divide-border">
            {experiment.runs.map((run) => (
              <section
                key={run.adapter_validation_id}
                aria-label={`${run.title} provenance`}
                className="min-w-0 space-y-3 py-4 first:pt-0"
              >
                <h5 className="text-sm font-semibold text-text">{run.title}</h5>
                <dl className="grid gap-3 text-xs text-text sm:grid-cols-2">
                  {[
                    ['Base validation', run.base_validation_id],
                    [`${FINE_TUNED_MODEL_LABEL} validation`, run.adapter_validation_id],
                    ['Base evaluation', run.base_evaluation_id],
                    [`${FINE_TUNED_MODEL_LABEL} evaluation`, run.adapter_evaluation_id],
                  ].map(([label, value]) => (
                    <div key={label} className="min-w-0 space-y-1">
                      <dt className="font-semibold">{label}</dt>
                      <dd className="font-mono [overflow-wrap:anywhere]">{value}</dd>
                    </div>
                  ))}
                </dl>
                {run.prompt_hashes.length ? (
                  <dl className="space-y-3 text-xs text-text">
                    {run.prompt_hashes.map((hash) => (
                      <div key={hash.sha256} className="space-y-1">
                        <dt className="font-semibold">
                          Identical prompt · {hash.criteria.join(', ')}
                        </dt>
                        <dd className="font-mono [overflow-wrap:anywhere]">{hash.sha256}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
              </section>
            ))}
          </div>
        </div>
      </details>
    </section>
  );
}
