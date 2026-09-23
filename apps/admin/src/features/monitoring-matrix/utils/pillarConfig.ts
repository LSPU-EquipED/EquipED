import type { TargetDomainId } from './matrixFormatters';

export interface PillarPresentationConfig {
  id: TargetDomainId;
  label: string;
  roleTitle: string;
  description: string;
}

export const PILLAR_CONFIGS: Record<TargetDomainId, PillarPresentationConfig> = {
  sme: {
    id: 'sme',
    label: 'Content Accuracy',
    roleTitle: 'Subject Matter Expert (SME)',
    description: 'Evaluation of domain terminology, concept depth, pedagogical validity, and topical accuracy.',
  },
  coordinator: {
    id: 'coordinator',
    label: 'Curriculum Alignment',
    roleTitle: 'Program Coordinator (PC)',
    description: 'Alignment with institutional syllabus, course learning outcomes (CLOs), and credit schedule.',
  },
  gad: {
    id: 'gad',
    label: 'Gender & Inclusivity',
    roleTitle: 'GAD Specialist',
    description: 'Gender-fair language, non-discriminatory framing, cultural sensitivity, and Universal Design.',
  },
  itso: {
    id: 'itso',
    label: 'Citations & IP',
    roleTitle: 'ITSO Specialist',
    description: 'Copyright compliance, fair use citations, intellectual property attribution, and plagiarism prevention.',
  },
};

/**
 * Formats numeric weight (0–1 or 0–100) into a percentage display string.
 * Returns 'Unknown' if the weight is missing or non-finite.
 */
export function formatPillarWeight(weight: number | null | undefined): string {
  if (weight == null || !Number.isFinite(weight)) {
    return 'Unknown';
  }
  // Weights are conventionally 0-1 (e.g. 0.35 => 35%), but tolerate percentages <= 100 if passed as integer
  const pct = weight <= 1 && weight >= 0 ? weight * 100 : weight;
  const rounded = Number.isInteger(pct) ? String(pct) : pct.toFixed(1).replace(/\.0$/, '');
  return `${rounded}%`;
}
