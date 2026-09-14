// Single source of truth for status -> label/color, mirroring the pattern
// evaluation/utils/scoreHelpers.ts uses for adjectival ratings (avoids the
// duplicated color logic Scorecard.tsx and MonitoringTable.tsx currently have).
import type { AlignmentStatus } from '../types';

const STATUS_LABELS: Record<AlignmentStatus, string> = {
  match: 'Match',
  'under-developed': 'Under-developed',
  'over-developed': 'Over-developed',
  not_addressed: 'Not addressed',
  not_observed: 'Not observed in evaluated pages',
};

const STATUS_BADGE_CLASSES: Record<AlignmentStatus, string> = {
  match: 'border-success/30 bg-success-soft text-success',
  'over-developed': 'border-info/30 bg-info-soft text-info',
  'under-developed': 'border-warning/30 bg-warning-soft text-warning',
  not_addressed: 'border-destructive/30 bg-destructive-soft text-destructive',
  not_observed: 'border-destructive/30 bg-destructive-soft text-destructive',
};

export function statusLabel(status: AlignmentStatus): string {
  return STATUS_LABELS[status];
}

export function statusBadgeClasses(status: AlignmentStatus): string {
  return STATUS_BADGE_CLASSES[status];
}
