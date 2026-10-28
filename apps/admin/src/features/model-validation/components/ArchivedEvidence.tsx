import { useState } from 'react';
import { Dropdown } from '@equiped/ui';
import type { ArchivedExperiment, ArchivedOutput } from '../archiveTypes';
import { FINE_TUNED_MODEL_LABEL } from '../utils/archivePresentation';

function Output({ label, value }: { label: string; value: ArchivedOutput }) {
  return (
    <section
      aria-label={`${label} archived explanation`}
      className="min-w-0 space-y-5 rounded-sm border border-border p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-3">
        <h4 className="text-sm font-semibold text-text">{label}</h4>
        <span className="text-sm font-semibold tabular-nums text-text">
          {value.score} <span className="font-normal text-text-muted">/ 4</span>
        </span>
        <p className="w-full text-xs text-text-muted">
          {value.status === 'repaired'
            ? 'Repaired model response'
            : value.status === 'ok'
              ? 'Model-scored response'
              : value.status === 'fallback'
                ? 'Fallback — not model reasoning'
                : 'Status unavailable'}
        </p>
      </div>
      <div>
        <h5 className="mb-2 text-xs font-semibold text-text">Stored source evidence</h5>
        {value.evidence?.length ? (
          value.evidence.map((quote, i) => (
            <blockquote
              key={i}
              className="mb-3 whitespace-pre-wrap border-l-2 border-border pl-3 text-sm leading-relaxed text-text [overflow-wrap:anywhere]"
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
  const runs = experiment.runs.filter((run) => run.criteria.length > 0);
  const run = runs[runIndex] ?? runs[0];
  if (!run) return <p className="text-sm text-text-muted">No archived evidence is available.</p>;
  const criterion = run.criteria.find((c) => c.id === criterionId) ?? run.criteria[0];
  return (
    <div className="@container/archive-evidence min-w-0 space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Dropdown
          id="archive-slm"
          label="SLM comparison"
          value={runIndex}
          onChange={setRunIndex}
          options={runs.map((r, i) => ({ value: i, label: r.title }))}
          size="md"
          containerClassName="min-w-0"
          className="w-full"
          menuClassName="w-full"
        />
        <Dropdown
          id="archive-criterion"
          label="Criterion"
          value={criterion.id}
          onChange={setCriterionId}
          options={run.criteria.map((c) => ({ value: c.id, label: `${c.id} — ${c.title}` }))}
          size="md"
          containerClassName="min-w-0"
          className="w-full"
          menuClassName="w-full"
        />
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 border-t border-border pt-5">
        <h3 className="min-w-0 text-sm font-semibold leading-relaxed text-text">
          {criterion.id} — {criterion.title}
        </h3>
        <p className="text-xs text-text-muted">
          {experiment.primary_criteria && !experiment.primary_criteria.includes(criterion.id)
            ? 'Base stability control'
            : 'Synthetic target'}
          : <strong className="text-text">{criterion.expected}/4</strong>
        </p>
      </div>
      <div className="grid min-w-0 gap-5 @min-[44rem]/archive-evidence:grid-cols-2">
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
