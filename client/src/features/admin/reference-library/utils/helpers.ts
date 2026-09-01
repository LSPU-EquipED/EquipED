import { POLICY_AREA_LABELS, type PolicyArea } from '@/shared/types/documents';

export const referenceTypeLabels: Record<string, string> = {
  syllabus: 'Syllabus',
  curriculum: 'Curriculum',
};

export const policyAreaLabelMap = POLICY_AREA_LABELS as Record<PolicyArea, string>;

export function isPolicyArea(value: string | null | undefined): value is PolicyArea {
  return value !== null && value !== undefined && value in policyAreaLabelMap;
}
export function processingStatusClass(status: string): string {
  if (status === 'PROCESSED') return 'bg-success-soft text-success border border-success/20';
  if (status === 'FAILED') return 'bg-destructive-soft text-destructive border border-destructive/20';
  return 'bg-warning-soft text-warning border border-warning/20';
}

export function healthBadgeClass(healthy: boolean): string {
  return healthy
    ? 'bg-success-soft text-success border border-success/20'
    : 'bg-destructive-soft text-destructive border border-destructive/20';
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
