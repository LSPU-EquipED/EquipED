import type { ClientDocument } from '@equiped/types';
import type { SlmDisplayActionType } from '@/shared/utils/slmDisplayStatus';

/**
 * Truncates a document ID to standard compact ledger notation (first 8 ... last 5).
 * IDs with 16 or fewer characters are returned as-is.
 */
export function truncateId(id: string): string {
  if (id.length <= 16) return id;
  return `${id.slice(0, 8)}...${id.slice(-5)}`;
}

/**
 * Converts backend document processing status enum into human-readable inspector label.
 */
export function formatProcessingStatus(status: string | null | undefined): string {
  switch (status) {
    case 'PROCESSED':
      return 'Indexed';
    case 'PROCESSING':
      return 'Processing';
    case 'PENDING':
      return 'Pending';
    case 'FAILED':
      return 'Failed';
    case 'CLEANUP_PENDING':
      return 'Cleaning up';
    default:
      return status || 'Not specified';
  }
}

/**
 * Computes a human-friendly title prioritizing Course Title + Lesson Title over raw filename/title.
 */
export function getHumanReadableTitle(
  doc: Pick<ClientDocument, 'title' | 'courseTitle' | 'lessonTitle'>,
): string {
  if (doc.courseTitle && doc.lessonTitle) {
    return `${doc.courseTitle} — ${doc.lessonTitle}`;
  }
  return doc.lessonTitle || doc.courseTitle || doc.title;
}

/**
 * Derives descriptive evaluation copy based on SLM actionType.
 */
export function getEvaluationDescription(actionType: SlmDisplayActionType): string {
  switch (actionType) {
    case 'view_results':
      return 'Multi-agent evaluation has been completed for this learning module. Review the consolidated findings, scores, evidence, and recommendations.';
    case 'start_evaluation':
      return 'This course module is indexed and ready for multi-agent evaluation by Subject Matter Expert (SME), Program Coordinator, GAD, and ITSO specialists.';
    case 'view_progress':
      return 'Specialist evaluation pipeline is actively running across domain rubrics.';
    case 'processing':
      return 'Document ingestion is in progress. Once indexing finishes, the module can be submitted for multi-agent evaluation.';
    case 'upload_failed':
      return 'Ingestion failed for this document. Please re-upload a clean, valid PDF.';
    case 'inspect_failure':
    case 'checking_status':
    case 'status_unavailable':
      return 'Multi-agent evaluation status for this module.';
  }
}

/**
 * Derives button label for evaluation action.
 */
export function getEvaluationActionLabel(
  actionType: SlmDisplayActionType,
  fallbackLabel: string,
): string {
  if (actionType === 'view_results') {
    return 'Open Evaluation';
  }
  if (actionType === 'start_evaluation') {
    return 'Launch Evaluation';
  }
  return fallbackLabel;
}

/**
 * Formats uploaded timestamp for module inspector display.
 */
export function formatInspectorDate(dateString: string | null | undefined): string {
  if (!dateString) return 'Not specified';
  return new Date(dateString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
