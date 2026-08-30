import { Warning, CheckCircle, ArrowSquareOut, Spinner, XCircle } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { buildApiUrl } from '@/shared/api/http';
import type { AlignmentRun } from '../types';
import { levelLabels, levelStyles } from '../utils/alignmentPresentation';

type AlignmentResultViewProps = {
  run: AlignmentRun | null;
  emptyMessage?: string;
  linkSlmEvidence?: boolean;
};

function LevelIcon({ run }: { run: AlignmentRun }) {
  if (run.alignment_level === 'MEETS') {
    return <CheckCircle className="size-6 text-success" aria-hidden="true" />;
  }
  if (run.alignment_level === 'PARTIALLY_MEETS') {
    return <Warning className="size-6 text-warning" aria-hidden="true" />;
  }
  return <XCircle className="size-6 text-destructive" aria-hidden="true" />;
}

export function AlignmentResultView({
  run,
  emptyMessage = 'No syllabus alignment result is available.',
  linkSlmEvidence = false,
}: AlignmentResultViewProps) {
  if (!run) return <p className="p-5 text-sm leading-relaxed text-text-muted">{emptyMessage}</p>;
  if (run.status === 'QUEUED' || run.status === 'RUNNING') {
    return (
      <div className="flex items-center gap-3 p-5 text-sm font-semibold text-text">
        <Spinner className="size-5 animate-spin text-primary" aria-hidden="true" />
        Alignment is running. This page updates automatically.
      </div>
    );
  }

  const artifact = run.alignment_artifact;
  const level = run.alignment_level ?? 'UNAVAILABLE';
  const style = levelStyles[level];

  return (
    <div>
      <section className={cn('border-b border-l-4 p-5', style.border, style.background)}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <LevelIcon run={run} />
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                Alignment level
              </p>
              <h2 className={`mt-1 text-2xl font-bold ${style.accent}`}>
                {levelLabels[level]}
              </h2>
            </div>
          </div>
          {artifact && (
            <div className={`rounded-sm border px-3 py-2 text-right ${style.badge}`}>
              <p className="text-xl font-bold tabular-nums">
                {artifact.aligned_topics} / {artifact.total_topics}
              </p>
              <p className="text-[11px] font-bold uppercase tracking-wide">Topics aligned</p>
            </div>
          )}
        </div>

        <div className="mt-5 max-w-4xl border-t border-current/15 pt-4">
          <h3 className="text-sm font-bold text-text">Why this level was assigned</h3>
          <p className="mt-2 text-sm leading-6 text-text">
            {run.justification || 'No detailed justification was recorded.'}
          </p>
        </div>

        <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-text-muted">
          <div>
            <dt className="inline font-semibold">Compared with: </dt>
            <dd className="inline">{run.syllabus_title ?? 'Selected syllabus'}</dd>
          </div>
          <div>
            <dt className="inline font-semibold">Completed: </dt>
            <dd className="inline">
              {run.completed_at ? new Date(run.completed_at).toLocaleString() : 'Unavailable'}
            </dd>
          </div>
        </dl>
        <a
          href={`${buildApiUrl(`/documents/${run.syllabus_document_id}/file`)}#page=1`}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-primary underline hover:text-primary-strong"
        >
          View source syllabus <ArrowSquareOut className="size-3" aria-hidden="true" />
        </a>
      </section>

      {artifact && (
        <div className="grid gap-5 p-5 lg:grid-cols-2">
          <TopicSection
            title="Aligned topics"
            empty="No aligned topics were recorded."
            tone="aligned"
            items={artifact.content_matches}
            linkSlmEvidence={linkSlmEvidence}
          />
          <TopicSection
            title="Topics outside the syllabus"
            empty="No topics outside the syllabus were recorded."
            tone="outside"
            items={artifact.unmatched_topics}
            linkSlmEvidence={linkSlmEvidence}
          />
        </div>
      )}
    </div>
  );
}

type TopicItem = NonNullable<AlignmentRun['alignment_artifact']>['unmatched_topics'][number] & {
  content_ref?: string;
  content_text?: string;
  page_number?: number | null;
};

function TopicSection({
  title,
  empty,
  tone,
  items,
  linkSlmEvidence,
}: {
  title: string;
  empty: string;
  tone: 'aligned' | 'outside';
  items: TopicItem[];
  linkSlmEvidence: boolean;
}) {
  const articleClass =
    tone === 'aligned'
      ? 'border-success/30 bg-success-soft/30'
      : 'border-destructive/30 bg-destructive-soft/30';
  return (
    <section>
      <h2 className="border-b border-border pb-2 text-base font-bold text-text">{title}</h2>
      <div className="mt-3 space-y-3">
        {items.length ? (
          items.map((item) => (
            <article key={item.topic_id} className={`rounded-sm border p-4 ${articleClass}`}>
              <h3 className="text-sm font-bold text-text">{item.topic}</h3>
              {linkSlmEvidence ? (
                <a
                  href={`#chunk-${item.slm_chunk_id}`}
                  className="mt-1 inline-block text-xs font-semibold text-primary underline hover:text-primary-strong"
                >
                  View SLM page {item.slm_page_number ?? '—'}
                </a>
              ) : (
                <p className="mt-1 text-xs font-semibold text-text-muted">
                  SLM page {item.slm_page_number ?? '—'}
                </p>
              )}
              <blockquote className="mt-2 border-l-2 border-border pl-3 text-xs leading-5 text-text-muted">
                “{item.slm_evidence}”
              </blockquote>
              {item.content_text && (
                <div className="mt-3 border-t border-border pt-3">
                  <p className="text-xs font-semibold text-success">
                    {item.content_ref || 'Syllabus course content'}, page {item.page_number ?? '—'}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-text">{item.content_text}</p>
                </div>
              )}
              <p className={`mt-3 text-xs leading-5 ${tone === 'outside' ? 'text-destructive font-medium' : 'text-text-muted'}`}>
                <strong>Reason:</strong> {item.rationale}
              </p>
            </article>
          ))
        ) : (
          <p className="text-sm text-text-muted">{empty}</p>
        )}
      </div>
    </section>
  );
}
