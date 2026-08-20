import { describe, expect, it } from 'vitest';
import type { ClientDocument } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import type { HomeEvaluationItem } from '../../types';
import {
  deriveAttentionItems,
  deriveFacultyHomeData,
  formatDateOnly,
  formatDateTime,
  getDocumentStatusBadge,
  getEvaluationStatusBadge,
  isActiveEvaluationStatus,
  isCompletedEvaluationStatus,
  isProcessingDocument,
} from '../homeData';

const mockDocuments: ClientDocument[] = [
  {
    documentId: 'doc-1',
    title: 'Data Structures Module 1',
    courseTitle: 'Data Structures and Algorithms',
    lessonTitle: null,
    sourceType: 'slm',
    program: 'BSCS',
    academicYear: '2024-2025',
    courseCode: 'CS101',
    pageCount: 15,
    processingStatus: 'PROCESSED',
    hasOcrPages: false,
    uploadedAt: '2026-08-20T10:00:00Z',
    chunks: [],
  },
  {
    documentId: 'doc-2',
    title: 'Web Dev Module 2',
    courseTitle: 'Web Development',
    lessonTitle: null,
    sourceType: 'slm',
    program: 'BSIT',
    academicYear: '2024-2025',
    courseCode: 'IT201',
    pageCount: 22,
    processingStatus: 'FAILED',
    hasOcrPages: false,
    uploadedAt: '2026-08-19T09:00:00Z',
    chunks: [],
  },
  {
    documentId: 'doc-3',
    title: 'Networking Module 3',
    courseTitle: 'Computer Networks',
    lessonTitle: null,
    sourceType: 'slm',
    program: 'BSIT',
    academicYear: '2024-2025',
    courseCode: 'IT301',
    pageCount: 18,
    processingStatus: 'PROCESSING',
    hasOcrPages: false,
    uploadedAt: '2026-08-21T08:00:00Z',
    chunks: [],
  },
  {
    documentId: 'doc-4',
    title: 'Operating Systems Module 4',
    courseTitle: 'Operating Systems',
    lessonTitle: null,
    sourceType: 'slm',
    program: 'BSCS',
    academicYear: '2024-2025',
    courseCode: 'CS301',
    pageCount: 25,
    processingStatus: 'PROCESSED',
    hasOcrPages: false,
    uploadedAt: '2026-08-21T11:00:00Z',
    chunks: [],
  },
];

const mockEvaluations: HomeEvaluationItem[] = [
  {
    evaluation_id: 'eval-1',
    document_id: 'doc-1',
    document_title: 'Data Structures Module 1',
    syllabus_id: 'syl-1',
    curriculum_id: 'curr-1',
    status: 'PROCESSING',
    submitted_at: '2026-08-21T09:30:00Z',
  },
  {
    evaluation_id: 'eval-2',
    document_id: 'doc-10',
    document_title: 'Database Systems Module 1',
    syllabus_id: 'syl-2',
    curriculum_id: 'curr-2',
    status: 'COMPLETED',
    submitted_at: '2026-08-20T14:00:00Z',
    completed_at: '2026-08-20T14:05:00Z',
  },
  {
    evaluation_id: 'eval-3',
    document_id: 'doc-11',
    document_title: 'Software Engineering Module 1',
    syllabus_id: 'syl-3',
    curriculum_id: 'curr-3',
    status: 'FAILED',
    error_message: 'ITSO agent timeout',
    submitted_at: '2026-08-19T11:00:00Z',
  },
  {
    evaluation_id: 'eval-4',
    document_id: 'doc-12',
    document_title: 'AI Fundamentals Module 1',
    syllabus_id: 'syl-4',
    curriculum_id: 'curr-4',
    status: 'COMPLETED_PARTIAL',
    submitted_at: '2026-08-18T16:00:00Z',
    completed_at: '2026-08-18T16:04:00Z',
  },
];

describe('homeData helpers', () => {
  it('identifies processing document statuses', () => {
    expect(isProcessingDocument('PENDING')).toBe(true);
    expect(isProcessingDocument('PROCESSING')).toBe(true);
    expect(isProcessingDocument('CLEANUP_PENDING')).toBe(true);
    expect(isProcessingDocument('PROCESSED')).toBe(false);
    expect(isProcessingDocument('FAILED')).toBe(false);
  });

  it('identifies active evaluation statuses across full lifecycle', () => {
    expect(isActiveEvaluationStatus('SUBMITTED')).toBe(true);
    expect(isActiveEvaluationStatus('PREPROCESSING')).toBe(true);
    expect(isActiveEvaluationStatus('EVALUATING')).toBe(true);
    expect(isActiveEvaluationStatus('SYNTHESIZING')).toBe(true);
    expect(isActiveEvaluationStatus('PENDING')).toBe(true);
    expect(isActiveEvaluationStatus('PROCESSING')).toBe(true);
    expect(isActiveEvaluationStatus('COMPLETED')).toBe(false);
    expect(isActiveEvaluationStatus('COMPLETED_PARTIAL')).toBe(false);
    expect(isActiveEvaluationStatus('FAILED')).toBe(false);
  });

  it('identifies completed evaluation statuses', () => {
    expect(isCompletedEvaluationStatus('COMPLETED')).toBe(true);
    expect(isCompletedEvaluationStatus('COMPLETED_PARTIAL')).toBe(true);
    expect(isCompletedEvaluationStatus('FAILED')).toBe(false);
    expect(isCompletedEvaluationStatus('PROCESSING')).toBe(false);
  });

  it('derives attention items sorted newest-first without jargon', () => {
    const attention = deriveAttentionItems(mockDocuments, mockEvaluations);
    expect(attention).toHaveLength(2);

    expect(attention[0].id).toBe('eval-eval-3');
    expect(attention[0].type).toBe('evaluation_failed');
    expect(attention[0].title).toBe('Software Engineering Module 1');
    expect(attention[0].targetUrl).toBe('/evaluations/eval-3');

    expect(attention[1].id).toBe('doc-doc-2');
    expect(attention[1].type).toBe('document_failed');
    expect(attention[1].title).toBe('Web Dev Module 2');
    expect(attention[1].detail).toContain('Document processing failed during upload');
    expect(attention[1].targetUrl).toBe('/documents');
  });

  it('derives faculty home data without misleading global aggregate metrics', () => {
    const homeData = deriveFacultyHomeData(mockDocuments, mockEvaluations);

    expect(homeData.recentIssues).toHaveLength(2);
    expect(homeData.activeEvaluation?.evaluation_id).toBe('eval-1');
    expect(homeData.hasEvaluations).toBe(true);
    expect(homeData.recentSlms).toHaveLength(4);
    expect(homeData.recentEvaluations).toHaveLength(4);
  });

  it('selects unevaluated PROCESSED document as ready banner candidate after batch status succeeds', () => {
    // doc-1 is already evaluating (eval-1), doc-4 is PROCESSED with NO evaluation
    const latestEvals: Record<string, LatestEvaluationItem> = {
      'doc-1': {
        document_id: 'doc-1',
        evaluation_id: 'eval-1',
        status: 'PROCESSING',
        submitted_at: '2026-08-21T09:30:00Z',
      },
    };

    // When there are no active evals, doc-4 should be selected as latestReadyDocument
    const terminalEvals: HomeEvaluationItem[] = [
      {
        evaluation_id: 'eval-2',
        document_id: 'doc-10',
        document_title: 'Database Systems Module 1',
        syllabus_id: 'syl-2',
        curriculum_id: 'curr-2',
        status: 'COMPLETED',
        submitted_at: '2026-08-20T14:00:00Z',
      },
    ];

    const homeData = deriveFacultyHomeData(
      mockDocuments,
      terminalEvals,
      latestEvals,
      true, // isLatestEvalsSuccess
    );

    // doc-4 is PROCESSED and has no entry in latestEvals => selected as ready candidate!
    // Even though faculty has another evaluation (eval-2), no global suppression occurs!
    expect(homeData.latestReadyDocument?.documentId).toBe('doc-4');
  });

  it('never sets latestReadyDocument when batch status request is not yet successful', () => {
    const terminalEvals: HomeEvaluationItem[] = [];
    const homeData = deriveFacultyHomeData(
      mockDocuments,
      terminalEvals,
      {},
      false, // isLatestEvalsSuccess is false (loading/error)
    );

    // Must be null to avoid flashing false Ready state
    expect(homeData.latestReadyDocument).toBeNull();
  });

  it('selects PREPROCESSING and SYNTHESIZING as active banner candidates', () => {
    const preprocessingEvals: HomeEvaluationItem[] = [
      {
        evaluation_id: 'eval-pre',
        document_id: 'doc-1',
        document_title: 'Preprocessing SLM',
        syllabus_id: 'syl-1',
        curriculum_id: 'curr-1',
        status: 'PREPROCESSING',
        submitted_at: '2026-08-21T10:00:00Z',
      },
    ];
    const preHomeData = deriveFacultyHomeData(mockDocuments, preprocessingEvals);
    expect(preHomeData.activeEvaluation?.evaluation_id).toBe('eval-pre');

    const synthesizingEvals: HomeEvaluationItem[] = [
      {
        evaluation_id: 'eval-syn',
        document_id: 'doc-1',
        document_title: 'Synthesizing SLM',
        syllabus_id: 'syl-1',
        curriculum_id: 'curr-1',
        status: 'SYNTHESIZING',
        submitted_at: '2026-08-21T10:00:00Z',
      },
    ];
    const synHomeData = deriveFacultyHomeData(mockDocuments, synthesizingEvals);
    expect(synHomeData.activeEvaluation?.evaluation_id).toBe('eval-syn');
  });

  it('provides honest status badges with accessible contrast', () => {
    const completedBadge = getEvaluationStatusBadge('COMPLETED');
    expect(completedBadge.label).toBe('Completed');
    expect(completedBadge.className).toContain('text-[#15803d]');

    const partialBadge = getEvaluationStatusBadge('COMPLETED_PARTIAL');
    expect(partialBadge.label).toBe('Completed (Partial)');

    const failedBadge = getEvaluationStatusBadge('FAILED');
    expect(failedBadge.label).toBe('Failed');

    const preBadge = getEvaluationStatusBadge('PREPROCESSING');
    expect(preBadge.label).toBe('Preprocessing');

    const evalBadge = getEvaluationStatusBadge('EVALUATING');
    expect(evalBadge.label).toBe('Evaluating');

    const synBadge = getEvaluationStatusBadge('SYNTHESIZING');
    expect(synBadge.label).toBe('Synthesizing');

    const subBadge = getEvaluationStatusBadge('SUBMITTED');
    expect(subBadge.label).toBe('Submitted');

    const docReadyBadge = getDocumentStatusBadge('PROCESSED');
    expect(docReadyBadge.label).toBe('Ready');
    expect(docReadyBadge.className).toContain('text-[#15803d]');

    const docFailedBadge = getDocumentStatusBadge('FAILED');
    expect(docFailedBadge.label).toBe('Failed');
  });

  it('formats dates safely with hoisted formatters', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateOnly(null)).toBe('—');
    expect(formatDateTime('2026-08-21T09:30:00Z')).toContain('2026');
    expect(formatDateOnly('2026-08-21T09:30:00Z')).toContain('2026');
  });
});
