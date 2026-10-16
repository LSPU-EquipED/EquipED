import type { ClientDocument } from '@equiped/types';
import type { LatestEvaluationItem } from '@equiped/types';
import type { FacultyHomeData, HomeEvaluationItem } from '../types';

const dateOnlyFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
});

export const isProcessingDocument = (status: ClientDocument['processingStatus']): boolean =>
  status === 'PENDING' || status === 'PROCESSING' || status === 'CLEANUP_PENDING';

export const isActiveEvaluationStatus = (status: string): boolean => {
  const normalized = status.toUpperCase();
  return (
    normalized === 'SUBMITTED' ||
    normalized === 'PREPROCESSING' ||
    normalized === 'EVALUATING' ||
    normalized === 'SYNTHESIZING' ||
    normalized === 'PENDING' ||
    normalized === 'PROCESSING'
  );
};

export function deriveFacultyHomeData(
  documents: ClientDocument[],
  evaluations: HomeEvaluationItem[],
  latestEvalsByDocId: Record<string, LatestEvaluationItem> = {},
): FacultyHomeData {
  // Active evaluation: first in-progress evaluation from evaluations list or from latestEvalsByDocId
  let activeEvaluation: HomeEvaluationItem | null =
    evaluations.find((e) => isActiveEvaluationStatus(e.status)) ?? null;

  if (!activeEvaluation) {
    for (const doc of documents) {
      const latest = latestEvalsByDocId[doc.documentId];
      if (latest && isActiveEvaluationStatus(latest.status)) {
        activeEvaluation = {
          evaluation_id: latest.evaluation_id,
          document_id: latest.document_id,
          document_title: doc.title,
          syllabus_id: '',
          curriculum_id: '',
          status: latest.status,
          target_agent: latest.target_agent,
          submitted_at: latest.submitted_at,
          completed_at: latest.completed_at ?? undefined,
          error_message: latest.error_message ?? undefined,
        };
        break;
      }
    }
  }

  return {
    activeEvaluation,
  };
}

export function formatDateOnly(dateStr?: string | null): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return dateOnlyFormatter.format(d);
  } catch {
    return dateStr;
  }
}

export function getEvaluationStatusBadge(status: string): {
  label: string;
  className: string;
} {
  const normalized = status.toUpperCase();
  switch (normalized) {
    case 'COMPLETED':
      return {
        label: 'Completed',
        className: 'bg-success-soft text-success border border-success/30',
      };
    case 'COMPLETED_PARTIAL':
      return {
        label: 'Completed (Partial)',
        className: 'bg-warning-soft text-warning border border-warning/30',
      };
    case 'FAILED':
      return {
        label: 'Failed',
        className: 'bg-destructive-soft text-destructive border border-destructive/30',
      };
    case 'PREPROCESSING':
      return {
        label: 'Preprocessing',
        className: 'bg-info-soft text-info border border-info/30',
      };
    case 'EVALUATING':
      return {
        label: 'Evaluating',
        className: 'bg-info-soft text-info border border-info/30',
      };
    case 'SYNTHESIZING':
      return {
        label: 'Synthesizing',
        className: 'bg-info-soft text-info border border-info/30',
      };
    case 'SUBMITTED':
      return {
        label: 'Submitted',
        className: 'bg-surface-subtle text-text-muted border border-border',
      };
    case 'PROCESSING':
      return {
        label: 'Processing',
        className: 'bg-info-soft text-info border border-info/30',
      };
    case 'PENDING':
      return {
        label: 'Queued',
        className: 'bg-surface-subtle text-text-muted border border-border',
      };
    default:
      return {
        label: status.replace(/_/g, ' '),
        className: 'bg-surface-subtle text-text-muted border border-border',
      };
  }
}
