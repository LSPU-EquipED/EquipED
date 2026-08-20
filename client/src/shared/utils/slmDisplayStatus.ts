import type { ClientDocument, DocumentProcessingStatus } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';

export type SlmDisplayActionType =
  | 'view_progress'
  | 'inspect_failure'
  | 'view_results'
  | 'start_evaluation'
  | 'processing'
  | 'upload_failed'
  | 'checking_status'
  | 'status_unavailable';

export interface SlmDisplayStatus {
  badgeLabel: string;
  badgeClass: string;
  showSpinner: boolean;
  isClickable: boolean;
  actionType: SlmDisplayActionType;
  actionLabel: string;
  actionUrl: string | null;
  ariaLabel: string;
  tooltip?: string;
}

export interface SlmStatusQueryState {
  isLoading?: boolean;
  isError?: boolean;
  isSuccess?: boolean;
}

export function isProcessingDocumentStatus(status: DocumentProcessingStatus): boolean {
  return status === 'PENDING' || status === 'PROCESSING' || status === 'CLEANUP_PENDING';
}

export function isEvaluatingStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  const normalized = status.toUpperCase();
  return (
    normalized === 'SUBMITTED' ||
    normalized === 'PREPROCESSING' ||
    normalized === 'EVALUATING' ||
    normalized === 'SYNTHESIZING' ||
    normalized === 'PENDING' ||
    normalized === 'PROCESSING'
  );
}

export function isEvaluationCompletedStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  const normalized = status.toUpperCase();
  return (
    normalized === 'COMPLETED' ||
    normalized === 'COMPLETED_PARTIAL' ||
    normalized.startsWith('COMPLETED')
  );
}

export function isEvaluationFailedStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  return status.toUpperCase() === 'FAILED';
}

export function getSlmDisplayStatus(
  document: Pick<ClientDocument, 'documentId' | 'title' | 'processingStatus'>,
  latestEval: LatestEvaluationItem | undefined,
  queryState: SlmStatusQueryState = {},
): SlmDisplayStatus {
  const { processingStatus, documentId, title } = document;

  // Precedence 1: Document is PENDING/PROCESSING/CLEANUP_PENDING => Processing
  if (isProcessingDocumentStatus(processingStatus)) {
    return {
      badgeLabel: 'Processing',
      badgeClass: 'bg-[#f2c811]/20 text-[#854d0e] border border-[#f2c811]/40',
      showSpinner: true,
      isClickable: false,
      actionType: 'processing',
      actionLabel: 'Processing',
      actionUrl: null,
      ariaLabel: `Document ${title} is currently processing`,
      tooltip: 'Processing in progress — check back shortly.',
    };
  }

  // Precedence 2: Document is FAILED => Upload Failed
  if (processingStatus === 'FAILED') {
    return {
      badgeLabel: 'Upload Failed',
      badgeClass: 'bg-[#b91c1c]/10 text-[#b91c1c] border border-[#b91c1c]/30',
      showSpinner: false,
      isClickable: false,
      actionType: 'upload_failed',
      actionLabel: 'Upload Failed',
      actionUrl: null,
      ariaLabel: `Document upload failed for ${title}`,
      tooltip: 'Document processing failed during upload. Document is not available for evaluation.',
    };
  }

  // From here on, document.processingStatus is PROCESSED.
  // Precedence 7 (loading): Latest-status request is loading => Checking Status (never falsely Ready)
  if (queryState.isLoading) {
    return {
      badgeLabel: 'Checking Status',
      badgeClass: 'bg-slate-100 text-slate-600 border border-slate-200',
      showSpinner: true,
      isClickable: false,
      actionType: 'checking_status',
      actionLabel: 'Checking Status',
      actionUrl: null,
      ariaLabel: `Checking evaluation status for ${title}`,
      tooltip: 'Checking evaluation status...',
    };
  }

  // Precedence 7 (error): Latest-status request failed => Status Unavailable
  if (queryState.isError) {
    return {
      badgeLabel: 'Status Unavailable',
      badgeClass: 'bg-slate-100 text-slate-600 border border-slate-200',
      showSpinner: false,
      isClickable: false,
      actionType: 'status_unavailable',
      actionLabel: 'Status Unavailable',
      actionUrl: null,
      ariaLabel: `Evaluation status unavailable for ${title}`,
      tooltip: 'Unable to retrieve latest evaluation status.',
    };
  }

  // If latest evaluation exists:
  if (latestEval) {
    // Precedence 3: Latest eval is active => Evaluating -> workspace (View Progress)
    if (isEvaluatingStatus(latestEval.status)) {
      return {
        badgeLabel: 'Evaluating',
        badgeClass: 'bg-[#1b3b87]/10 text-[#1b3b87] border border-[#1b3b87]/30',
        showSpinner: true,
        isClickable: true,
        actionType: 'view_progress',
        actionLabel: 'View Progress',
        actionUrl: `/documents/${documentId}/evaluation`,
        ariaLabel: `View evaluation progress for ${title}`,
      };
    }

    // Precedence 4: Latest eval is FAILED => Evaluation Failed -> workspace (Inspect Evaluation)
    if (isEvaluationFailedStatus(latestEval.status)) {
      return {
        badgeLabel: 'Evaluation Failed',
        badgeClass: 'bg-[#b91c1c]/10 text-[#b91c1c] border border-[#b91c1c]/30',
        showSpinner: false,
        isClickable: true,
        actionType: 'inspect_failure',
        actionLabel: 'Inspect Evaluation',
        actionUrl: `/documents/${documentId}/evaluation`,
        ariaLabel: `Inspect evaluation for ${title}`,
      };
    }

    // Precedence 5: Latest eval is COMPLETED => Evaluated -> workspace (Open Evaluation)
    if (isEvaluationCompletedStatus(latestEval.status)) {
      return {
        badgeLabel: 'Evaluated',
        badgeClass: 'bg-[#15803d]/10 text-[#15803d] border border-[#15803d]/30',
        showSpinner: false,
        isClickable: true,
        actionType: 'view_results',
        actionLabel: 'Open Evaluation',
        actionUrl: `/documents/${documentId}/evaluation`,
        ariaLabel: `Open evaluation for ${title}`,
      };
    }
  }

  // Precedence 6: Processed + no eval after successful batch response => Ready to Evaluate -> /documents/$documentId/evaluation
  return {
    badgeLabel: 'Ready to Evaluate',
    badgeClass: 'bg-[#15803d]/10 text-[#15803d] border border-[#15803d]/30',
    showSpinner: false,
    isClickable: true,
    actionType: 'start_evaluation',
    actionLabel: 'Evaluate',
    actionUrl: `/documents/${documentId}/evaluation`,
    ariaLabel: `Start evaluation for ${title}`,
  };
}
