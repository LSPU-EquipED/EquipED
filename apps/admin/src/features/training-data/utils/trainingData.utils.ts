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

export type ReadinessTier = 'empty' | 'single-evaluation' | 'small' | 'reasonable';

export const RULE_OF_THUMB_NOTE = `${RECOMMENDED_MIN_PAIRS} pairs is a rule of thumb, not a guarantee: consistent corrections matter more than the count.`;

export const SEEDED_DATA_NOTE =
  "Counts cover the whole database and include any seeded test data, which can't be told apart here.";

export function getReadinessTier(
  pairCount: number,
  evaluationCount: number,
): { tier: ReadinessTier; message: string } {
  if (pairCount <= 0) {
    return {
      tier: 'empty',
      message: 'No trainable pairs yet. Starting a job would be refused.',
    };
  }
  if (evaluationCount < 2) {
    return {
      tier: 'single-evaluation',
      message: 'All pairs come from one evaluation, so nothing can be held out to check the adapter.',
    };
  }
  if (pairCount < RECOMMENDED_MIN_PAIRS) {
    return {
      tier: 'small',
      message: `Under ${RECOMMENDED_MIN_PAIRS} pairs: fine for a smoke test, unlikely to show real learning.`,
    };
  }
  return {
    tier: 'reasonable',
    message: 'Enough volume to attempt a training run.',
  };
}

export function getReviewerNote(reviewerCount: number): string | null {
  return reviewerCount === 1
    ? "All corrections come from one reviewer, so an adapter would learn that person's judgement only."
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
  const noun = examined === 1 ? 'generation' : 'generations';
  const base = `${examined} ${noun} examined: ${pairCount} became pairs`;
  if (skippedTotal === 0) return `${base}, none skipped.`;
  const detail =
    reasons.length === 1
      ? formatSkipReason(reasons[0][0]).toLowerCase()
      : reasons.map(([reason, count]) => `${count} ${formatSkipReason(reason).toLowerCase()}`).join(', ');
  return `${base}, ${skippedTotal} skipped (${detail}).`;
}

export function shortHash(hash: string | null | undefined): string {
  return hash ? hash.slice(0, 8) : '—';
}

export function formatSize(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  if (mb < 1) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(1)} MB`;
}
