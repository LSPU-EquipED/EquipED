import type { ClientDocument } from '@equiped/types';

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
