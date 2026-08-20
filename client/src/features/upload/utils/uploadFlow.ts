import type { DocumentProcessingStatus, DocumentUploadResponse } from '@/shared/types/documents';

/**
 * Pure decision helpers for the faculty SLM upload flow. Kept free of
 * router/hook imports so the guard and redirect rules are unit-testable.
 */

export type UploadRouteAccess = { allowed: true } | { allowed: false; redirectTo: '/login' | '/admin' };

/**
 * The /upload route is faculty-only. Admins upload SLMs through the Model
 * Validation workflow instead, and unauthenticated users must sign in first.
 */
export function resolveUploadRouteAccess(
  userRole: string | null | undefined,
): UploadRouteAccess {
  if (!userRole) {
    return { allowed: false, redirectTo: '/login' };
  }

  if (userRole === 'faculty') {
    return { allowed: true };
  }

  return { allowed: false, redirectTo: '/admin' };
}

/**
 * A successful SLM upload continues to the evaluation page only after the
 * document is fully processed. Non-terminal processing or failed results stay on upload.
 */
export function shouldNavigateToEvaluation(
  result: Pick<DocumentUploadResponse, 'processingStatus'> | null | undefined,
): boolean {
  return result?.processingStatus === 'PROCESSED';
}

/**
 * Check if the document processing status is a non-terminal in-progress state.
 */
export function isProcessingStatus(
  status: DocumentProcessingStatus | string | null | undefined,
): boolean {
  return status === 'PENDING' || status === 'PROCESSING' || status === 'CLEANUP_PENDING';
}

/**
 * Check if the document processing status is successfully processed.
 */
export function isTerminalSuccessStatus(
  status: DocumentProcessingStatus | string | null | undefined,
): boolean {
  return status === 'PROCESSED';
}

/**
 * Check if the document processing status is terminal failed.
 */
export function isFailedStatus(
  status: DocumentProcessingStatus | string | null | undefined,
): boolean {
  return status === 'FAILED';
}

/**
 * Validate that a file is a valid PDF by MIME type or file extension.
 */
export function isPdfFile(file: File | null | undefined): boolean {
  if (!file) {
    return false;
  }
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
}

export function evaluationRouteForDocument(documentId: string): string {
  return `/documents/${documentId}/evaluation`;
}
