import type { ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import type { ClientDocument, DocumentProcessingStatus } from '@/shared/types/documents';

export const sourceTypeLabels: Record<ClientDocument['sourceType'], string> = {
  slm: 'SLM',
  syllabus: 'Syllabus',
  rubric_sme: 'SME Rubric',
  rubric_coord: 'Coordinator Rubric',
  rubric_gad: 'GAD Rubric',
  rubric_itso: 'ITSO Rubric',
  curriculum: 'Curriculum',
};

export const statusConfig: Record<
  DocumentProcessingStatus,
  { label: string; badgeClass: string; icon?: ReactNode }
> = {
  PENDING: {
    label: 'Processing',
    badgeClass: 'bg-[#f2c811] text-[#1e293b]',
    icon: <Loader2 className="mr-1 size-3 animate-spin" aria-hidden="true" />,
  },
  PROCESSING: {
    label: 'Processing',
    badgeClass: 'bg-[#f2c811] text-[#1e293b]',
    icon: <Loader2 className="mr-1 size-3 animate-spin" aria-hidden="true" />,
  },
  PROCESSED: {
    label: 'Ready',
    badgeClass: 'bg-[#3b963e] text-white',
  },
  FAILED: {
    label: 'Failed',
    badgeClass: 'bg-[#b91c1c] text-white',
  },
};

export function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    year: 'numeric',
  }).format(new Date(value));
}
