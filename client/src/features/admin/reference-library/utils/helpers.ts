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
  if (status === 'PROCESSED') return 'bg-[#3b963e] text-white';
  if (status === 'FAILED') return 'bg-[#b91c1c] text-white';
  return 'bg-[#f2c811] text-[#1e293b]';
}

export function healthBadgeClass(healthy: boolean): string {
  return healthy
    ? 'bg-[#3b963e]/10 text-[#3b963e] border-[#3b963e]/20'
    : 'bg-[#b91c1c]/10 text-[#b91c1c] border-[#b91c1c]/20';
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
