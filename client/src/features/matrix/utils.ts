import type { MatrixDomainScoreBlock } from './types';

export function formatRevisionContext(
  domainScores: Record<string, MatrixDomainScoreBlock> | null | undefined,
): string {
  if (!domainScores || Object.keys(domainScores).length === 0) {
    return '—';
  }

  const blocks = Object.values(domainScores);
  const versions = Array.from(
    new Set(
      blocks
        .map((b) => b.version)
        .filter((v): v is number => typeof v === 'number' && Number.isFinite(v)),
    ),
  ).sort((a, b) => a - b);

  if (versions.length > 0) {
    return `Rev ${versions.join(', ')}`;
  }

  const hasAnySnapshot = blocks.some((b) => Boolean(b.form_snapshot_id));
  if (!hasAnySnapshot && blocks.length > 0) {
    return 'Legacy — form snapshot unavailable';
  }

  return '—';
}
