// Single source of truth for turning a check's summary counts into the
// compact chip line shown per history row, mirroring the pattern
// alignmentHelpers.ts uses for status -> label/color.
import type { AlignmentCheckSummary } from '../types';

const CHIP_ORDER: Array<{ key: keyof AlignmentCheckSummary; label: string }> = [
  { key: 'match', label: 'match' },
  { key: 'under_developed', label: 'under' },
  { key: 'over_developed', label: 'over' },
  { key: 'not_addressed', label: 'not addressed' },
];

export function formatSummaryChips(summary: AlignmentCheckSummary): string {
  return CHIP_ORDER.map(({ key, label }) => `${summary[key]} ${label}`).join(' · ');
}
