import { describe, expect, it } from 'vitest';
import type { ClientDocument } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import { getSlmDisplayStatus } from '../slmDisplayStatus';

const baseDoc: ClientDocument = {
  documentId: 'doc-123',
  title: 'Introduction to Computer Science',
  courseTitle: 'CS 101',
  lessonTitle: null,
  sourceType: 'slm',
  program: 'BSCS',
  academicYear: '2024-2025',
  courseCode: 'CS101',
  pageCount: 20,
  processingStatus: 'PROCESSED',
  hasOcrPages: false,
  uploadedAt: '2026-08-20T10:00:00Z',
  chunks: [],
};

describe('getSlmDisplayStatus - Truthful Display Precedence', () => {
  it('Precedence 1: returns Processing when document processingStatus is PENDING/PROCESSING', () => {
    const docPending = { ...baseDoc, processingStatus: 'PENDING' as const };
    const status = getSlmDisplayStatus(docPending, undefined, { isSuccess: true });
    expect(status.badgeLabel).toBe('Processing');
    expect(status.actionType).toBe('processing');
    expect(status.isClickable).toBe(false);
    expect(status.showSpinner).toBe(true);

    const docProcessing = { ...baseDoc, processingStatus: 'PROCESSING' as const };
    const statusProc = getSlmDisplayStatus(docProcessing, undefined, { isSuccess: true });
    expect(statusProc.badgeLabel).toBe('Processing');
    expect(statusProc.actionType).toBe('processing');
    expect(statusProc.isClickable).toBe(false);
  });

  it('Precedence 2: returns Upload Failed when document processingStatus is FAILED', () => {
    const docFailed = { ...baseDoc, processingStatus: 'FAILED' as const };
    const status = getSlmDisplayStatus(docFailed, undefined, { isSuccess: true });
    expect(status.badgeLabel).toBe('Upload Failed');
    expect(status.actionType).toBe('upload_failed');
    expect(status.isClickable).toBe(false);
    expect(status.showSpinner).toBe(false);
  });

  it('Precedence 7: returns Checking Status when status request is loading and never falsely Ready', () => {
    const status = getSlmDisplayStatus(baseDoc, undefined, { isLoading: true });
    expect(status.badgeLabel).toBe('Checking Status');
    expect(status.actionType).toBe('checking_status');
    expect(status.isClickable).toBe(false);
    expect(status.showSpinner).toBe(true);
    expect(status.badgeLabel).not.toBe('Ready to Evaluate');
  });

  it('Precedence 7: returns Status Unavailable when status request failed with error', () => {
    const status = getSlmDisplayStatus(baseDoc, undefined, { isError: true });
    expect(status.badgeLabel).toBe('Status Unavailable');
    expect(status.actionType).toBe('status_unavailable');
    expect(status.isClickable).toBe(false);
    expect(status.showSpinner).toBe(false);
  });

  it('Precedence 3: returns Evaluating and links to the workspace with View Progress when eval is active', () => {
    const activeEval: LatestEvaluationItem = {
      document_id: 'doc-123',
      evaluation_id: 'eval-active-1',
      status: 'EVALUATING',
      submitted_at: '2026-08-21T10:00:00Z',
    };
    const status = getSlmDisplayStatus(baseDoc, activeEval, { isSuccess: true });
    expect(status.badgeLabel).toBe('Evaluating');
    expect(status.actionType).toBe('view_progress');
    expect(status.actionLabel).toBe('View Progress');
    expect(status.actionUrl).toBe('/documents/doc-123/evaluation');
    expect(status.isClickable).toBe(true);
    expect(status.showSpinner).toBe(true);

    const preEval: LatestEvaluationItem = {
      ...activeEval,
      status: 'PREPROCESSING',
    };
    expect(getSlmDisplayStatus(baseDoc, preEval, { isSuccess: true }).badgeLabel).toBe('Evaluating');

    const synEval: LatestEvaluationItem = {
      ...activeEval,
      status: 'SYNTHESIZING',
    };
    expect(getSlmDisplayStatus(baseDoc, synEval, { isSuccess: true }).badgeLabel).toBe('Evaluating');
  });

  it('Precedence 4: returns Evaluation Failed and links to the workspace with Inspect Evaluation', () => {
    const failedEval: LatestEvaluationItem = {
      document_id: 'doc-123',
      evaluation_id: 'eval-fail-1',
      status: 'FAILED',
      submitted_at: '2026-08-21T09:00:00Z',
      error_message: 'Agent timeout',
    };
    const status = getSlmDisplayStatus(baseDoc, failedEval, { isSuccess: true });
    expect(status.badgeLabel).toBe('Evaluation Failed');
    expect(status.actionType).toBe('inspect_failure');
    expect(status.actionLabel).toBe('Inspect Evaluation');
    expect(status.actionUrl).toBe('/documents/doc-123/evaluation');
    expect(status.isClickable).toBe(true);
  });

  it('Precedence 5: returns Evaluated and links to the workspace with Open Evaluation when completed', () => {
    const completedEval: LatestEvaluationItem = {
      document_id: 'doc-123',
      evaluation_id: 'eval-done-1',
      status: 'COMPLETED',
      submitted_at: '2026-08-20T11:00:00Z',
      completed_at: '2026-08-20T11:05:00Z',
    };
    const status = getSlmDisplayStatus(baseDoc, completedEval, { isSuccess: true });
    expect(status.badgeLabel).toBe('Evaluated');
    expect(status.actionType).toBe('view_results');
    expect(status.actionLabel).toBe('Open Evaluation');
    expect(status.actionUrl).toBe('/documents/doc-123/evaluation');
    expect(status.isClickable).toBe(true);

    const partialEval: LatestEvaluationItem = {
      ...completedEval,
      status: 'COMPLETED_PARTIAL',
    };
    const partialStatus = getSlmDisplayStatus(baseDoc, partialEval, { isSuccess: true });
    expect(partialStatus.badgeLabel).toBe('Evaluated');
    expect(partialStatus.actionLabel).toBe('Open Evaluation');
    expect(partialStatus.actionUrl).toBe('/documents/doc-123/evaluation');
  });

  it('Precedence 6: returns Ready to Evaluate and links to workspace when processed with no eval after batch loads', () => {
    const status = getSlmDisplayStatus(baseDoc, undefined, { isSuccess: true });
    expect(status.badgeLabel).toBe('Ready to Evaluate');
    expect(status.actionType).toBe('start_evaluation');
    expect(status.actionLabel).toBe('Evaluate');
    expect(status.actionUrl).toBe('/documents/doc-123/evaluation');
    expect(status.isClickable).toBe(true);
    expect(status.showSpinner).toBe(false);
  });
});
