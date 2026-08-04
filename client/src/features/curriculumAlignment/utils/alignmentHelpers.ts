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
  match: 'border-[#3b963e]/30 bg-[#3b963e]/10 text-[#3b963e]',
  'over-developed': 'border-[#3eaed4]/30 bg-[#3eaed4]/10 text-[#3eaed4]',
  'under-developed': 'border-[#f2c811]/30 bg-[#f2c811]/10 text-[#8a6d00]',
  not_addressed: 'border-[#b91c1c]/30 bg-[#b91c1c]/10 text-[#b91c1c]',
  not_observed: 'border-[#b91c1c]/30 bg-[#b91c1c]/10 text-[#b91c1c]',
};

export function statusLabel(status: AlignmentStatus): string {
  return STATUS_LABELS[status];
}

export function statusBadgeClasses(status: AlignmentStatus): string {
  return STATUS_BADGE_CLASSES[status];
}
