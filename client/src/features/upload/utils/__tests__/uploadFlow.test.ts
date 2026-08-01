import { describe, expect, it } from 'vitest';
import {
  evaluationRouteForDocument,
  resolveUploadRouteAccess,
  shouldNavigateToEvaluation,
} from '../uploadFlow';

describe('resolveUploadRouteAccess', () => {
  it('allows faculty users onto /upload', () => {
    expect(resolveUploadRouteAccess('faculty')).toEqual({ allowed: true });
  });

  it('redirects admins away from /upload to /admin', () => {
    expect(resolveUploadRouteAccess('admin')).toEqual({
      allowed: false,
      redirectTo: '/admin',
    });
  });

  it('redirects unauthenticated users to /login', () => {
    expect(resolveUploadRouteAccess(null)).toEqual({ allowed: false, redirectTo: '/login' });
    expect(resolveUploadRouteAccess(undefined)).toEqual({ allowed: false, redirectTo: '/login' });
  });
});

describe('shouldNavigateToEvaluation', () => {
  it('navigates when the SLM upload finished processing', () => {
    expect(shouldNavigateToEvaluation({ processingStatus: 'PROCESSED' })).toBe(true);
  });

  it('stays on the upload experience when processing failed', () => {
    expect(shouldNavigateToEvaluation({ processingStatus: 'FAILED' })).toBe(false);
  });

  it('stays on the upload experience when no result is available', () => {
    expect(shouldNavigateToEvaluation(null)).toBe(false);
    expect(shouldNavigateToEvaluation(undefined)).toBe(false);
  });
});

describe('evaluationRouteForDocument', () => {
  it('builds the evaluation route for the uploaded document', () => {
    expect(evaluationRouteForDocument('doc-123')).toBe('/documents/doc-123/evaluation');
  });
});
