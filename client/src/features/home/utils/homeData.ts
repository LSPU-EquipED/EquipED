import type { ClientDocument } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import type { AttentionItem, FacultyHomeData, HomeEvaluationItem } from '../types';

const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});

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

export const isCompletedEvaluationStatus = (status: string): boolean => {
  const normalized = status.toUpperCase();
  return normalized === 'COMPLETED' || normalized === 'COMPLETED_PARTIAL';
};

export function deriveAttentionItems(
  documents: ClientDocument[],
  evaluations: HomeEvaluationItem[],
): AttentionItem[] {
  const items: AttentionItem[] = [];

  for (const doc of documents) {
    if (doc.processingStatus === 'FAILED') {
      items.push({
        id: `doc-${doc.documentId}`,
        type: 'document_failed',
        title: doc.title || 'Untitled SLM',
        detail: 'Document processing failed during upload. Please upload again.',
        timestamp: doc.uploadedAt,
        targetUrl: '/documents',
        actionLabel: 'View in My SLMs',
      });
    }
  }

  for (const ev of evaluations) {
    if (ev.status.toUpperCase() === 'FAILED') {
      items.push({
        id: `eval-${ev.evaluation_id}`,
        type: 'evaluation_failed',
        title: ev.document_title || `Evaluation ${ev.evaluation_id.slice(0, 8)}`,
        detail: ev.error_message || 'Automated evaluation failed.',
        timestamp: ev.submitted_at,
        targetUrl: `/evaluations/${ev.evaluation_id}`,
        actionLabel: 'Inspect Failure',
      });
    }
  }

  // Sort combined recent issues newest-first
  items.sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime();
    const timeB = new Date(b.timestamp).getTime();
    const safeA = isNaN(timeA) ? 0 : timeA;
    const safeB = isNaN(timeB) ? 0 : timeB;
    return safeB - safeA;
  });

  return items;
}

export function deriveFacultyHomeData(
  documents: ClientDocument[],
  evaluations: HomeEvaluationItem[],
  latestEvalsByDocId: Record<string, LatestEvaluationItem> = {},
  isLatestEvalsSuccess = false,
): FacultyHomeData {
  const recentIssues = deriveAttentionItems(documents, evaluations);

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
          submitted_at: latest.submitted_at,
          completed_at: latest.completed_at ?? undefined,
          error_message: latest.error_message ?? undefined,
        };
        break;
      }
    }
  }

  // Latest ready document: must be PROCESSED and have NO latest evaluation after status batch has successfully loaded
  let latestReadyDocument: ClientDocument | null = null;
  if (isLatestEvalsSuccess) {
    latestReadyDocument =
      documents.find((d) => d.processingStatus === 'PROCESSED' && !latestEvalsByDocId[d.documentId]) ??
      null;
  }

  const recentSlms = documents.slice(0, 5);
  const recentEvaluations = evaluations.slice(0, 5);

  return {
    recentIssues,
    activeEvaluation,
    latestReadyDocument,
    hasEvaluations: evaluations.length > 0,
    recentSlms,
    recentEvaluations,
  };
}

export function formatDateTime(dateStr?: string | null): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return dateTimeFormatter.format(d);
  } catch {
    return dateStr;
  }
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
        className: 'bg-[#15803d]/10 text-[#15803d] border border-[#15803d]/30',
      };
    case 'COMPLETED_PARTIAL':
      return {
        label: 'Completed (Partial)',
        className: 'bg-[#f2c811]/20 text-[#854d0e] border border-[#f2c811]/40',
      };
    case 'FAILED':
      return {
        label: 'Failed',
        className: 'bg-[#b91c1c]/10 text-[#b91c1c] border border-[#b91c1c]/30',
      };
    case 'PREPROCESSING':
      return {
        label: 'Preprocessing',
        className: 'bg-[#1b3b87]/10 text-[#1b3b87] border border-[#1b3b87]/30',
      };
    case 'EVALUATING':
      return {
        label: 'Evaluating',
        className: 'bg-[#1b3b87]/10 text-[#1b3b87] border border-[#1b3b87]/30',
      };
    case 'SYNTHESIZING':
      return {
        label: 'Synthesizing',
        className: 'bg-[#1b3b87]/10 text-[#1b3b87] border border-[#1b3b87]/30',
      };
    case 'SUBMITTED':
      return {
        label: 'Submitted',
        className: 'bg-slate-100 text-slate-700 border border-slate-300',
      };
    case 'PROCESSING':
      return {
        label: 'Processing',
        className: 'bg-[#1b3b87]/10 text-[#1b3b87] border border-[#1b3b87]/30',
      };
    case 'PENDING':
      return {
        label: 'Queued',
        className: 'bg-slate-100 text-slate-700 border border-slate-300',
      };
    default:
      return {
        label: status.replace(/_/g, ' '),
        className: 'bg-slate-100 text-slate-700 border border-slate-200',
      };
  }
}

export function getDocumentStatusBadge(status: ClientDocument['processingStatus']): {
  label: string;
  className: string;
} {
  switch (status) {
    case 'PROCESSED':
      return {
        label: 'Ready',
        className: 'bg-[#15803d]/10 text-[#15803d] border border-[#15803d]/30',
      };
    case 'FAILED':
      return {
        label: 'Failed',
        className: 'bg-[#b91c1c]/10 text-[#b91c1c] border border-[#b91c1c]/30',
      };
    case 'PENDING':
    case 'PROCESSING':
    case 'CLEANUP_PENDING':
      return {
        label: 'Processing',
        className: 'bg-[#f2c811]/20 text-[#854d0e] border border-[#f2c811]/40',
      };
    default:
      return {
        label: status,
        className: 'bg-slate-100 text-slate-700 border border-slate-200',
      };
  }
}
