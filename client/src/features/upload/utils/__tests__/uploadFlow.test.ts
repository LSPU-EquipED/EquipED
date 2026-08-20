import { describe, expect, it } from 'vitest';
import {
  evaluationRouteForDocument,
  isFailedStatus,
  isPdfFile,
  isProcessingStatus,
  isTerminalSuccessStatus,
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

  it('stays on the upload experience for non-terminal processing states', () => {
    expect(shouldNavigateToEvaluation({ processingStatus: 'PENDING' })).toBe(false);
    expect(shouldNavigateToEvaluation({ processingStatus: 'PROCESSING' })).toBe(false);
    expect(shouldNavigateToEvaluation({ processingStatus: 'CLEANUP_PENDING' })).toBe(false);
  });

  it('stays on the upload experience when processing failed', () => {
    expect(shouldNavigateToEvaluation({ processingStatus: 'FAILED' })).toBe(false);
  });

  it('stays on the upload experience when no result is available', () => {
    expect(shouldNavigateToEvaluation(null)).toBe(false);
    expect(shouldNavigateToEvaluation(undefined)).toBe(false);
  });
});

describe('isProcessingStatus', () => {
  it('identifies non-terminal in-progress statuses correctly', () => {
    expect(isProcessingStatus('PENDING')).toBe(true);
    expect(isProcessingStatus('PROCESSING')).toBe(true);
    expect(isProcessingStatus('CLEANUP_PENDING')).toBe(true);
  });

  it('returns false for terminal or empty statuses', () => {
    expect(isProcessingStatus('PROCESSED')).toBe(false);
    expect(isProcessingStatus('FAILED')).toBe(false);
    expect(isProcessingStatus(null)).toBe(false);
    expect(isProcessingStatus(undefined)).toBe(false);
  });
});

describe('isTerminalSuccessStatus', () => {
  it('identifies PROCESSED as terminal success', () => {
    expect(isTerminalSuccessStatus('PROCESSED')).toBe(true);
  });

  it('returns false for non-PROCESSED statuses', () => {
    expect(isTerminalSuccessStatus('PENDING')).toBe(false);
    expect(isTerminalSuccessStatus('PROCESSING')).toBe(false);
    expect(isTerminalSuccessStatus('CLEANUP_PENDING')).toBe(false);
    expect(isTerminalSuccessStatus('FAILED')).toBe(false);
    expect(isTerminalSuccessStatus(null)).toBe(false);
  });
});

describe('isFailedStatus', () => {
  it('identifies FAILED as failed', () => {
    expect(isFailedStatus('FAILED')).toBe(true);
  });

  it('returns false for non-FAILED statuses', () => {
    expect(isFailedStatus('PENDING')).toBe(false);
    expect(isFailedStatus('PROCESSING')).toBe(false);
    expect(isFailedStatus('CLEANUP_PENDING')).toBe(false);
    expect(isFailedStatus('PROCESSED')).toBe(false);
    expect(isFailedStatus(null)).toBe(false);
  });
});

describe('isPdfFile', () => {
  it('accepts files with application/pdf MIME type', () => {
    const file = new File(['content'], 'sample.pdf', { type: 'application/pdf' });
    expect(isPdfFile(file)).toBe(true);
  });

  it('accepts files with .pdf extension even if MIME type is missing/generic', () => {
    const file = new File(['content'], 'learning-module.pdf', { type: '' });
    expect(isPdfFile(file)).toBe(true);
    const fileCaps = new File(['content'], 'LEARNING-MODULE.PDF', { type: 'application/octet-stream' });
    expect(isPdfFile(fileCaps)).toBe(true);
  });

  it('rejects non-PDF files', () => {
    const docx = new File(['content'], 'syllabus.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
    expect(isPdfFile(docx)).toBe(false);

    const png = new File(['content'], 'diagram.png', { type: 'image/png' });
    expect(isPdfFile(png)).toBe(false);

    const txt = new File(['content'], 'notes.txt', { type: 'text/plain' });
    expect(isPdfFile(txt)).toBe(false);

    expect(isPdfFile(null)).toBe(false);
    expect(isPdfFile(undefined)).toBe(false);
  });
});

describe('evaluationRouteForDocument', () => {
  it('builds the evaluation route for the uploaded document', () => {
    expect(evaluationRouteForDocument('doc-123')).toBe('/documents/doc-123/evaluation');
  });
});
