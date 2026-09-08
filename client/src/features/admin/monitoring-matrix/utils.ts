import type { StatusVariant } from '@/shared/constants/theme';
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

export function getStatusVariant(status: string): StatusVariant {
  const s = status.toUpperCase();
  if (s === 'FAILED' || s === 'ERROR') return 'destructive';
  if (s.startsWith('COMPLETED')) return 'success';
  if (s === 'EVALUATING' || s === 'PREPROCESSING' || s === 'SYNTHESIZING' || s === 'PROCESSING') return 'info';
  if (s === 'SUBMITTED' || s === 'PENDING' || s === 'QUEUED') return 'warning';
  return 'neutral';
}

export function statusClass(status: string): string {
  const s = status.toUpperCase();
  if (s === 'FAILED' || s === 'ERROR') {
    return 'bg-destructive-soft text-destructive border-destructive/20';
  }
  if (s.startsWith('COMPLETED')) {
    return 'bg-success-soft text-success border-success/20';
  }
  if (s === 'EVALUATING' || s === 'PREPROCESSING' || s === 'SYNTHESIZING' || s === 'PROCESSING') {
    return 'bg-info-soft text-info border-info/20';
  }
  if (s === 'SUBMITTED' || s === 'PENDING' || s === 'QUEUED') {
    return 'bg-warning-soft text-warning border-warning/20';
  }
  return 'bg-surface-subtle text-text-muted border-border';
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

export function ratingClass(rating: string | null | undefined): string {
  switch (rating) {
    case 'Very Satisfactory':
      return 'bg-success-soft text-success border-success/20';
    case 'Satisfactory':
      return 'bg-info-soft text-info border-info/20';
    case 'Needs Improvement':
      return 'bg-warning-soft text-warning border-warning/20';
    case 'Poor':
      return 'bg-destructive-soft text-destructive border-destructive/20';
    default:
      return 'bg-surface-subtle text-text-muted border-border';
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

export function getCompletedDomainCount(
  domainScores: Record<string, MatrixDomainScoreBlock> | null | undefined,
): number {
  if (!domainScores) return 0;
  return TARGET_DOMAIN_ORDER.filter((domainId) => domainScores[domainId] != null).length;
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
  return `${base} (${completed}/${total} DOMAINS)`;
}

export function formatDomainScore(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const fixed = value.toFixed(2);
  return fixed.endsWith('.00') ? String(Math.round(value)) : fixed;
}
