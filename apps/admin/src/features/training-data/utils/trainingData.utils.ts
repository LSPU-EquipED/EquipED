import type { ReadinessSummary, TrainingJobItem, TrainingSummary } from '../types';

export function formatCountdown(expiresAtIso: string, now: number): string {
  const diffMs = new Date(expiresAtIso).getTime() - now;
  if (diffMs <= 0) return 'Expired';
  const totalMinutes = Math.floor(diffMs / 60_000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h remaining`;
  if (hours > 0) return `${hours}h ${minutes}m remaining`;
  return `${minutes}m remaining`;
}

export const RECOMMENDED_MIN_PAIRS = 20;

export const RULE_OF_THUMB_NOTE = `${RECOMMENDED_MIN_PAIRS} correction examples is a rule of thumb, not a guarantee: consistent corrections matter more than the count.`;

export const SEEDED_DATA_NOTE =
  "Counts cover the whole database and include any seeded test data, which can't be told apart here.";

export function getReadinessTier(pairCount: number, evaluationCount: number): ReadinessSummary {
  if (pairCount <= 0) {
    return {
      tier: 'empty',
      message: 'No correction examples yet. A training run cannot be started.',
    };
  }
  if (evaluationCount < 2) {
    return {
      tier: 'single-evaluation',
      message:
        'All examples come from one evaluation, so none can be set aside to check the fine-tuned model.',
    };
  }
  if (pairCount < RECOMMENDED_MIN_PAIRS) {
    return {
      tier: 'small',
      message: `Under ${RECOMMENDED_MIN_PAIRS} correction examples: fine for a quick test, unlikely to show real learning.`,
    };
  }
  return {
    tier: 'reasonable',
    message: 'Enough examples to try a training run.',
  };
}

export function getReviewerNote(reviewerCount: number): string | null {
  return reviewerCount === 1
    ? "All corrections come from one reviewer, so a fine-tuned model would learn that person's judgement only."
    : null;
}

export type LatestJobComparison =
  | { kind: 'no-jobs' }
  | { kind: 'identical' }
  | { kind: 'changed'; from: number; to: number }
  | { kind: 'unknown' };

export function compareToLatestJob(
  readiness: { pair_count: number; pairs_sha256: string },
  latestJob: { pair_count?: number | null; pairs_sha256?: string | null } | undefined,
): LatestJobComparison {
  if (!latestJob) return { kind: 'no-jobs' };
  if (latestJob.pairs_sha256 == null || latestJob.pair_count == null) return { kind: 'unknown' };
  if (latestJob.pairs_sha256 === readiness.pairs_sha256) return { kind: 'identical' };
  return {
    kind: 'changed',
    from: latestJob.pair_count,
    to: readiness.pair_count,
  };
}

export function describeComparison(comparison: LatestJobComparison): string | null {
  switch (comparison.kind) {
    case 'identical':
      return 'Unchanged since the latest run; starting again uses the same examples.';
    case 'changed':
      return `Since the latest run: ${comparison.from} → ${comparison.to} correction examples.`;
    case 'unknown':
      return "The previous run's examples are unavailable for comparison.";
    case 'no-jobs':
      return null;
  }
}

const SKIP_REASON_LABELS: Record<string, string> = {
  no_reviewer_feedback: 'No reviewer feedback',
};

export function formatSkipReason(reason: string): string {
  const known = SKIP_REASON_LABELS[reason];
  if (known) return known;
  const spaced = reason.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function totalSkipped(skipped: Record<string, number>): number {
  return Object.values(skipped).reduce((sum, n) => sum + n, 0);
}

export function describeFunnel(pairCount: number, skipped: Record<string, number>): string {
  const reasons = Object.entries(skipped).filter(([, count]) => count > 0);
  const skippedTotal = totalSkipped(skipped);
  const examined = pairCount + skippedTotal;
  const noun = examined === 1 ? 'AI result' : 'AI results';
  const base = `${examined} ${noun} examined: ${pairCount} became correction examples`;
  if (skippedTotal === 0) return `${base}, none skipped.`;
  const detail =
    reasons.length === 1
      ? formatSkipReason(reasons[0][0]).toLowerCase()
      : reasons
          .map(([reason, count]) => `${count} ${formatSkipReason(reason).toLowerCase()}`)
          .join(', ');
  return `${base}, ${skippedTotal} skipped (${detail}).`;
}

export function formatSize(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  if (mb < 1) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(1)} MB`;
}

function isNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

const fixed = (value: number, digits = 2) => value.toFixed(digits);
const percent = (value: number) => `${Math.round(value * 100)}%`;

export function buildTrainingSummaryEntries(
  summary: TrainingSummary | null | undefined,
): [string, string][] {
  if (!summary) return [];
  const entries: [string, string][] = [];
  const first = summary.first;
  const last = summary.last;
  const heldout = summary.heldout;

  const lastMargin = last?.margin;
  const firstMargin = first?.margin;
  if (isNumber(lastMargin)) {
    const stepsDiffer = first?.step !== last?.step;
    const bothStepsMissing = first?.step == null && last?.step == null;
    const showStart =
      isNumber(firstMargin) && (stepsDiffer || (bothStepsMissing && firstMargin !== lastMargin));
    entries.push([
      'Preference margin',
      showStart ? `${fixed(firstMargin)} → ${fixed(lastMargin)}` : fixed(lastMargin),
    ]);
  }
  const lastAccuracy = last?.accuracy;
  if (isNumber(lastAccuracy)) entries.push(['Preference accuracy', percent(lastAccuracy)]);
  const lastLoss = last?.loss;
  if (isNumber(lastLoss)) entries.push(['Training loss', fixed(lastLoss, 3)]);
  if (isNumber(summary.steps)) {
    entries.push([
      'Steps',
      isNumber(summary.epochs)
        ? `${summary.steps} (${summary.epochs} ${summary.epochs === 1 ? 'epoch' : 'epochs'})`
        : `${summary.steps}`,
    ]);
  }
  const heldoutMargin = heldout?.margin;
  if (isNumber(heldoutMargin)) entries.push(['Held-out margin', fixed(heldoutMargin)]);
  const heldoutAccuracy = heldout?.accuracy;
  if (isNumber(heldoutAccuracy)) entries.push(['Held-out accuracy', percent(heldoutAccuracy)]);
  const heldoutPairs = heldout?.pair_count;
  if (isNumber(heldoutPairs)) entries.push(['Held-out pairs', `${heldoutPairs}`]);
  return entries;
}

export const STALE_AFTER_SECONDS = 15 * 60;

const RUN_STAGE_LABELS: Record<string, string> = {
  starting: 'Starting',
  training: 'Training',
  sending_model: 'Sending model',
  converting: 'Converting file',
  sending_file: 'Sending file',
  finished: 'Finished',
  failed: 'Failed',
};

export function isRunActive(job: Partial<TrainingJobItem>): boolean {
  return !!job.run_stage && job.run_stage !== 'finished' && job.run_stage !== 'failed';
}

/** A fresh run with no report yet is watched for as long as its download link lives. */
export const WAITING_POLL_WINDOW_MS = 24 * 60 * 60 * 1000;
/** A run silent for this long is treated as abandoned and no longer polled. */
export const POLL_GIVE_UP_AFTER_SECONDS = 2 * 60 * 60;
/** Upload tokens expire after 7 days; nothing newer than this can still report. */
export const RUN_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * Should the job list keep refreshing for this run? Pure: `now` is injected.
 * Separate from isRunActive (which drives the stale warning), because a run can
 * be "active" yet abandoned, and a run that has not reported yet is waiting.
 */
export function shouldPollRun(job: Partial<TrainingJobItem>, now: number): boolean {
  const created = job.created_at ? Date.parse(job.created_at) : NaN;
  const age = now - created; // NaN when created_at is unreadable
  if (!job.run_stage) {
    return job.status !== 'completed' && age >= 0 && age <= WAITING_POLL_WINDOW_MS;
  }
  // An unreadable date skips only the 7-day cap; the silence cap still applies.
  return (
    isRunActive(job) &&
    !(age > RUN_MAX_AGE_MS) &&
    (job.seconds_since_report ?? 0) < POLL_GIVE_UP_AFTER_SECONDS
  );
}

function formatAge(seconds: number): string {
  if (seconds < 60) return 'updated just now';
  if (seconds < 3600) return `updated ${Math.floor(seconds / 60)} min ago`;
  return `updated ${Math.floor(seconds / 3600)} h ago`;
}

export interface RunProgress {
  label: string;
  detail: string | null;
  stale: boolean;
  failed: boolean;
}

export function describeRunProgress(job: TrainingJobItem): RunProgress | null {
  if (!job.run_stage) return null;
  const parts: string[] = [];
  if (job.run_stage === 'training' && job.run_step != null && job.run_total != null) {
    parts.push(`step ${job.run_step} of ${job.run_total}`);
  }
  if (job.run_stage === 'failed' && job.run_message) parts.push(job.run_message);
  if (job.seconds_since_report != null) parts.push(formatAge(job.seconds_since_report));
  return {
    label: RUN_STAGE_LABELS[job.run_stage] ?? job.run_stage,
    detail: parts.length > 0 ? parts.join(' · ') : null,
    stale: isRunActive(job) && (job.seconds_since_report ?? 0) >= STALE_AFTER_SECONDS,
    failed: job.run_stage === 'failed',
  };
}
