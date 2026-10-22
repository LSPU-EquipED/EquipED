import { useState } from 'react';
import type { ArchivedExperiment, ArchivedOutput } from '../archiveTypes';
import { FINE_TUNED_MODEL_LABEL } from '../utils/archivePresentation';

function Output({ label, value }: { label: string; value: ArchivedOutput }) {
  return (
    <section aria-label={`${label} archived explanation`} className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-3">
        <h4 className="font-semibold text-text">
          {label} <span className="ml-2 tabular-nums">{value.score}/4</span>
        </h4>
        <span className="text-xs text-text-muted">
          {value.status === 'repaired'
            ? 'Repaired model response'
            : value.status === 'ok'
              ? 'Model-scored response'
              : value.status === 'fallback'
                ? 'Fallback — not model reasoning'
                : 'Status unavailable'}
        </span>
      </div>
      <div>
        <h5 className="mb-2 text-xs font-semibold text-text">Stored source evidence</h5>
        {value.evidence?.length ? (
          value.evidence.map((quote, i) => (
            <blockquote
              key={i}
              className="mb-2 whitespace-pre-wrap rounded-sm bg-surface-subtle/50 p-3 text-sm leading-relaxed text-text [overflow-wrap:anywhere]"
            >
              {quote}
            </blockquote>
          ))
        ) : (
          <p className="text-sm text-text-muted">Evidence not stored.</p>
        )}
      </div>
      <div>
        <h5 className="mb-2 text-xs font-semibold text-text">Captured model reasoning</h5>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-text [overflow-wrap:anywhere]">
          {value.status === 'fallback'
            ? 'Model reasoning is unavailable for this fallback.'
            : (value.reasoning ?? 'Reasoning not stored.')}
        </p>
      </div>
      {typeof value.quote_exact_in_claimed_chunk === 'boolean' ? (
        <p className="text-xs text-text-muted">
          Quote grounding:{' '}
          {value.quote_exact_in_claimed_chunk
            ? 'Exact quotation found in the cited source chunk.'
            : 'Exact quotation not found in the cited source chunk.'}
        </p>
      ) : null}
      {!value.reasoning && value.stored_justification ? (
        <div>
          <h5 className="mb-2 text-xs font-semibold text-text">
            Stored justification · separate field
          </h5>
          <p className="text-sm text-text">{value.stored_justification}</p>
        </div>
      ) : null}
    </section>
  );
}

export function ArchivedEvidence({ experiment }: { experiment: ArchivedExperiment }) {
  const [runIndex, setRunIndex] = useState(0);
  const [criterionId, setCriterionId] = useState('OP-05');
  const run = experiment.runs[runIndex];
  const criterion = run.criteria.find((c) => c.id === criterionId) ?? run.criteria[0];
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-1.5 text-xs font-semibold text-text">
          SLM comparison
          <select
            className="block min-h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-normal text-text focus-visible:outline-2 focus-visible:outline-ring"
            value={runIndex}
            onChange={(e) => setRunIndex(Number(e.target.value))}
          >
            {experiment.runs.map((r, i) => (
              <option key={r.adapter_validation_id} value={i}>
                {r.title}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-xs font-semibold text-text">
          Criterion
          <select
            className="block min-h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-normal text-text focus-visible:outline-2 focus-visible:outline-ring"
            value={criterion.id}
            onChange={(e) => setCriterionId(e.target.value)}
          >
            {run.criteria.map((c) => (
              <option key={c.id} value={c.id}>
                {c.id} — {c.title}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold text-text">
          {criterion.id} — {criterion.title}
        </h3>
        <p className="text-xs text-text-muted">
          {experiment.primary_criteria && !experiment.primary_criteria.includes(criterion.id)
            ? 'Base stability control'
            : 'Synthetic target'}
          : <strong className="text-text">{criterion.expected}/4</strong>
        </p>
      </div>
      <div className="grid min-w-0 gap-6 md:grid-cols-2">
        <Output label="Base" value={criterion.base} />
        <Output label={FINE_TUNED_MODEL_LABEL} value={criterion.adapter} />
      </div>
      {criterion.audit_note ? (
        <aside className="rounded-sm bg-info-soft p-3 text-sm leading-relaxed text-text">
          {criterion.audit_note.replace(/\badapter\b/gi, 'fine-tuned model')}{' '}
          <span className="block pt-1 text-xs">
            Recorded audit interpretation; not an expert-verified label.
          </span>
        </aside>
      ) : null}
    </div>
  );
}
