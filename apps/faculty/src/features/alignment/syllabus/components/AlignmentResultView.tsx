import { Warning, CheckCircle, ArrowSquareOut, Spinner, XCircle, Info } from '@phosphor-icons/react';
import { cn, Skeleton } from '@equiped/ui';
import { buildApiUrl } from '@equiped/api-client';
import type { AlignmentRun } from '../types';
import { levelLabels, levelStyles } from '../utils/alignmentPresentation';

export function AlignmentResultViewSkeleton() {
  return (
    <div
      className="divide-y divide-border"
      role="status"
      aria-label="Loading syllabus alignment result"
      aria-busy="true"
    >
      {/* Institutional Hero Banner Skeleton */}
      <section className="border-b p-5 sm:p-6 bg-surface-subtle/30">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <Skeleton className="size-8 rounded-sm shrink-0" />
            <div className="space-y-1.5">
              <Skeleton className="h-2.5 w-24" />
              <Skeleton className="h-6 w-40" />
            </div>
          </div>
          <div className="rounded-sm border border-border bg-surface px-3.5 py-2 space-y-1">
            <Skeleton className="h-6 w-16" />
            <Skeleton className="h-2 w-20" />
          </div>
        </div>

        <div className="mt-4 rounded-sm border border-border/60 bg-surface/80 p-3.5 space-y-2">
          <Skeleton className="h-3 w-36" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
        </div>

        <div className="mt-3.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-border/40 pt-3">
          <Skeleton className="h-3 w-48" />
          <Skeleton className="h-3 w-32" />
        </div>
      </section>

      {/* Topics List Skeleton */}
      <section className="p-4 sm:p-6 space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="rounded-sm border border-border bg-surface p-4 space-y-2.5"
            >
              <div className="flex items-center justify-between gap-3">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-5 w-20 rounded-xs" />
              </div>
              <Skeleton className="h-3 w-5/6" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

type AlignmentResultViewProps = {
  run: AlignmentRun | null;
  emptyMessage?: string;
  linkSlmEvidence?: boolean;
  isLoading?: boolean;
};

function LevelIcon({ run }: { run: AlignmentRun }) {
  if (run.alignment_level === 'MEETS') {
    return <CheckCircle className="size-5 text-success" aria-hidden="true" />;
  }
  if (run.alignment_level === 'PARTIALLY_MEETS') {
    return <Warning className="size-5 text-warning" aria-hidden="true" />;
  }
  return <XCircle className="size-5 text-destructive" aria-hidden="true" />;
}

export function AlignmentResultView({
  run,
  emptyMessage = 'No syllabus alignment result is available.',
  linkSlmEvidence = false,
  isLoading = false,
}: AlignmentResultViewProps) {
  if (isLoading) {
    return <AlignmentResultViewSkeleton />;
  }

  if (!run) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <Info className="mb-2 size-8 text-text-muted" aria-hidden="true" />
        <p className="max-w-md text-xs leading-relaxed text-text-muted">{emptyMessage}</p>
      </div>
    );
  }

  if (run.status === 'QUEUED' || run.status === 'RUNNING') {
    return (
      <div className="flex items-center gap-3 p-6 text-xs font-semibold text-text">
        <Spinner className="size-4 animate-spin text-primary" aria-hidden="true" />
        <span>Alignment is running. This page updates automatically.</span>
      </div>
    );
  }

  const artifact = run.alignment_artifact;
  const level = run.alignment_level ?? 'UNAVAILABLE';
  const style = levelStyles[level];

  return (
    <div className="divide-y divide-border">
      {/* Institutional Hero Banner */}
      <section className={cn('border-b p-5 sm:p-6', style.border, style.background)}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-sm border border-border bg-surface p-1.5 shadow-none">
              <LevelIcon run={run} />
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Alignment level
              </p>
              <h2 className={`mt-0.5 text-xl font-bold ${style.accent}`}>
                {levelLabels[level]}
              </h2>
            </div>
          </div>
          {artifact && (
            <div className={`rounded-sm border px-3.5 py-2 text-right ${style.badge}`}>
              <p className="text-xl font-bold tabular-nums">
                {artifact.aligned_topics} / {artifact.total_topics}
              </p>
              <p className="text-[10px] font-bold uppercase tracking-wider">Topics aligned</p>
            </div>
          )}
        </div>

        <div className="mt-4 rounded-sm border border-border/60 bg-surface/80 p-3.5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text">Why this level was assigned</h3>
          <p className="mt-1.5 text-xs leading-relaxed text-text">
            {run.justification || 'No detailed justification was recorded.'}
          </p>
        </div>

        <div className="mt-3.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-border/40 pt-3 text-xs text-text-muted">
          <dl className="flex flex-wrap gap-x-5 gap-y-1.5">
            <div>
              <dt className="inline font-semibold">Compared with: </dt>
              <dd className="inline font-medium text-text">{run.syllabus_title ?? 'Selected syllabus'}</dd>
            </div>
            <div>
              <dt className="inline font-semibold">Completed: </dt>
              <dd className="inline tabular-nums">
                {run.completed_at ? new Date(run.completed_at).toLocaleString() : 'Unavailable'}
              </dd>
            </div>
          </dl>
          {run.syllabus_document_id && (
            <a
              href={`${buildApiUrl(`/documents/${run.syllabus_document_id}/file`)}#page=1`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-semibold text-primary transition-colors hover:text-primary-strong"
            >
              <span>View source syllabus</span>
              <ArrowSquareOut className="size-3.5" aria-hidden="true" />
            </a>
          )}
        </div>
      </section>

      {/* Ledger Grid: Aligned Topics vs Topics Outside Syllabus */}
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
  return (
    <section className="flex flex-col">
      <div className="flex items-center justify-between border-b border-border pb-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-text">{title}</h2>
        <span
          className={cn(
            'rounded-xs px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider',
            tone === 'aligned'
              ? 'border border-success/30 bg-success-soft text-success'
              : 'border border-destructive/30 bg-destructive-soft text-destructive',
          )}
        >
          {items.length} {items.length === 1 ? 'topic' : 'topics'}
        </span>
      </div>
      <div className="mt-3 space-y-3">
        {items.length ? (
          items.map((item) => (
            <article
              key={item.topic_id}
              className={cn(
                'rounded-sm border p-3.5 transition-colors',
                tone === 'aligned'
                  ? 'border-border bg-surface hover:border-success/40'
                  : 'border-border bg-surface hover:border-destructive/40',
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xs font-bold text-text">{item.topic}</h3>
                {linkSlmEvidence ? (
                  <a
                    href={`#chunk-${item.slm_chunk_id}`}
                    className="inline-flex items-center gap-1 rounded-xs border border-border bg-surface-subtle px-2 py-0.5 text-[11px] font-semibold text-primary transition-colors hover:bg-surface hover:text-primary-strong"
                  >
                    <span>View SLM page {item.slm_page_number ?? '—'}</span>
                    <ArrowSquareOut className="size-3" aria-hidden="true" />
                  </a>
                ) : (
                  <span className="rounded-xs border border-border bg-surface-subtle px-2 py-0.5 text-[11px] font-semibold text-text-muted">
                    SLM page {item.slm_page_number ?? '—'}
                  </span>
                )}
              </div>

              <blockquote className="mt-2 rounded-xs border-l-2 border-border bg-surface-subtle/50 px-3 py-2 text-xs italic leading-relaxed text-text-muted">
                “{item.slm_evidence}”
              </blockquote>

              {item.content_text && (
                <div className="mt-3 rounded-xs border border-border bg-surface-subtle/30 p-2.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-success">
                    <CheckCircle className="size-3.5 shrink-0" aria-hidden="true" />
                    <span>
                      {item.content_ref || 'Syllabus course content'}, page {item.page_number ?? '—'}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-text">{item.content_text}</p>
                </div>
              )}

              <p
                className={cn(
                  'mt-2.5 text-xs leading-relaxed',
                  tone === 'outside' ? 'font-medium text-destructive' : 'text-text-muted',
                )}
              >
                <strong className="font-semibold text-text">Reason:</strong> {item.rationale}
              </p>
            </article>
          ))
        ) : (
          <div className="rounded-sm border border-dashed border-border p-6 text-center text-xs text-text-muted">
            {empty}
          </div>
        )}
      </div>
    </section>
  );
}
