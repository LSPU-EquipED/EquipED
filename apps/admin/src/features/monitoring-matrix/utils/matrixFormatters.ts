import type { StatusVariant } from '@equiped/ui';
import type { MatrixDomainScoreBlock } from '../types';

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

export function getRatingVariant(rating: string | null | undefined): StatusVariant {
  switch (rating) {
    case 'Very Satisfactory':
      return 'success';
    case 'Satisfactory':
      return 'info';
    case 'Needs Improvement':
      return 'warning';
    case 'Poor':
      return 'destructive';
    default:
      return 'neutral';
  }
}

export const TARGET_DOMAIN_ORDER = ['sme', 'coordinator', 'gad', 'itso'] as const;

export type TargetDomainId = (typeof TARGET_DOMAIN_ORDER)[number];

const TARGET_DOMAIN_SHORT_LABEL: Record<TargetDomainId, string> = {
  sme: 'SME',
  coordinator: 'Coord',
  gad: 'GAD',
  itso: 'ITSO',
};

export function domainShortLabel(domainId: string): string {
  if (
    domainId === 'sme' ||
    domainId === 'coordinator' ||
    domainId === 'gad' ||
    domainId === 'itso'
  ) {
    return TARGET_DOMAIN_SHORT_LABEL[domainId];
  }
  return domainId;
}

export function isDomainBlockEvaluated(
  block: MatrixDomainScoreBlock | null | undefined,
): boolean {
  if (!block) return false;
  const status = typeof block.status === 'string' ? block.status.toUpperCase() : '';
  if (status !== 'OK' && status !== 'COMPLETED') return false;
  if (block.subtotal == null || typeof block.subtotal !== 'number') return false;
  return Number.isFinite(block.subtotal) && block.subtotal >= 0 && block.subtotal <= 4;
}

export function getCompletedDomainCount(
  domainScores: Record<string, MatrixDomainScoreBlock> | null | undefined,
): number {
  if (!domainScores) return 0;
  return TARGET_DOMAIN_ORDER.filter((domainId) => isDomainBlockEvaluated(domainScores[domainId])).length;
}

export interface DomainProgress {
  completed: number;
  total: number;
}

export function getDomainProgress(
  domainScores: Record<string, MatrixDomainScoreBlock> | null | undefined,
): DomainProgress {
  return { completed: getCompletedDomainCount(domainScores), total: TARGET_DOMAIN_ORDER.length };
}

export function formatProgressStatus(
  evaluationStatus: string,
  domainScores: Record<string, MatrixDomainScoreBlock> | null | undefined,
): string {
  const base = evaluationStatus.replace(/_/g, ' ');
  if (evaluationStatus.toUpperCase() !== 'IN_PROGRESS') return base;
  const { completed, total } = getDomainProgress(domainScores);
  return `${base} (${completed}/${total})`;
}

export function formatDomainScore(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const fixed = value.toFixed(2);
  return fixed.endsWith('.00') ? String(Math.round(value)) : fixed;
}
