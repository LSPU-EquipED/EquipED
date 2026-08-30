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
  policy: 'Policy',
};

export const statusConfig: Record<
  DocumentProcessingStatus,
  { label: string; badgeClass: string; icon?: ReactNode }
> = {
  PENDING: {
    label: 'Processing',
    badgeClass: 'bg-warning-soft text-warning border border-warning/20',
    icon: <Loader2 className="mr-1 size-3 animate-spin" aria-hidden="true" />,
  },
  PROCESSING: {
    label: 'Processing',
    badgeClass: 'bg-warning-soft text-warning border border-warning/20',
    icon: <Loader2 className="mr-1 size-3 animate-spin" aria-hidden="true" />,
  },
  PROCESSED: {
    label: 'Ready',
    badgeClass: 'bg-success-soft text-success border border-success/20',
  },
  FAILED: {
    label: 'Failed',
    badgeClass: 'bg-destructive-soft text-destructive border border-destructive/20',
  },
  CLEANUP_PENDING: {
    label: 'Cleanup pending',
    badgeClass: 'bg-warning-soft text-warning border border-warning/20',
    icon: <Loader2 className="mr-1 size-3 animate-spin" aria-hidden="true" />,
  },
};

const unknownStatusConfig = {
  label: 'Unavailable',
  badgeClass: 'bg-surface-subtle text-text-muted border border-border',
};

export function getStatusMeta(status: string | null | undefined) {
  return statusConfig[status as DocumentProcessingStatus] ?? unknownStatusConfig;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    year: 'numeric',
  }).format(new Date(value));
}
