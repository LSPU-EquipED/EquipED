import type { DocumentUploadResponse } from '@/shared/types/documents';

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
 * document is fully processed. Failed or pending results stay on upload.
 */
export function shouldNavigateToEvaluation(
  result: Pick<DocumentUploadResponse, 'processingStatus'> | null | undefined,
): boolean {
  return result?.processingStatus === 'PROCESSED';
}

export function evaluationRouteForDocument(documentId: string): string {
  return `/documents/${documentId}/evaluation`;
}
