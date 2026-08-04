import { describe, expect, it } from 'vitest';
import type { ClientDocument, DocumentProcessingStatus } from '@/shared/types/documents';
import { ApiError } from '@/shared/api/http';
import type { AlignmentCheck } from '../../types';
import {
  alignmentSelectionReducer,
  buildCoverageBanner,
  buildDisplayedSummary,
  getAlignmentDocumentEligibility,
  getAlignmentRequestErrorState,
  getCoverageMetadata,
  getEvidenceNavigation,
  type AlignmentSelectionState,
} from '../alignmentState';

describe('alignmentSelectionReducer', () => {
  it('clears active check when document changes', () => {
    const state: AlignmentSelectionState = {
      documentId: 'doc-1',
      courseId: 'course-1',
      activeCheckId: 'check-old',
    };

    const nextState = alignmentSelectionReducer(state, {
      type: 'setDocument',
      documentId: 'doc-2',
    });

    expect(nextState).toMatchObject({
      documentId: 'doc-2',
      activeCheckId: null,
      courseId: 'course-1',
    });
  });

  it('clears active check when course changes', () => {
    const state: AlignmentSelectionState = {
      documentId: 'doc-1',
      courseId: 'course-1',
      activeCheckId: 'check-old',
    };

    const nextState = alignmentSelectionReducer(state, {
      type: 'setCourse',
      courseId: 'course-2',
    });

    expect(nextState).toMatchObject({
      courseId: 'course-2',
      activeCheckId: null,
      documentId: 'doc-1',
    });
  });
});

describe('document eligibility', () => {
  const baseDocument: ClientDocument = {
    documentId: 'doc-1',
    title: 'SLM File',
    sourceType: 'slm',
    processingStatus: 'PROCESSED',
    program: 'BS InfoTech',
    courseTitle: null,
    lessonTitle: null,
    academicYear: null,
    courseCode: null,
    pageCount: null,
    hasOcrPages: true,
    uploadedAt: new Date().toISOString(),
    chunks: [],
  };

  it('filters out non-SLM / unprocessed docs for run eligibility', () => {
    expect(getAlignmentDocumentEligibility(baseDocument).eligible).toBe(true);

    expect(
      getAlignmentDocumentEligibility({
        ...baseDocument,
        sourceType: 'reference',
        documentId: 'doc-2',
      } as unknown as ClientDocument,
    ).eligible,
    ).toBe(false);

    expect(
      getAlignmentDocumentEligibility({
        ...baseDocument,
        sourceType: 'slm',
        processingStatus: 'PENDING' as DocumentProcessingStatus,
        documentId: 'doc-3',
      } as unknown as ClientDocument,
    ).eligible,
    ).toBe(false);

    expect(
      getAlignmentDocumentEligibility({
        ...baseDocument,
        sourceType: 'slm',
        processingStatus: 'PROCESSED',
        program: 'BSIT',
        documentId: 'doc-4',
      } as unknown as ClientDocument,
    ).eligible,
    ).toBe(true);
  });
});

describe('request error mapping', () => {
  it('maps statuses to distinct alignment request states', () => {
    const apiError = new ApiError('program mismatch', {
      status: 422,
      payload: null,
      detail: 'program mismatch',
    });

    const mapped422 = getAlignmentRequestErrorState(apiError as never);
    expect(mapped422?.kind).toBe('program_mismatch');

    const mapped429 = getAlignmentRequestErrorState(
      new ApiError('rate limit', {
        status: 429,
        payload: null,
        detail: 'rate limit',
        headers: { 'retry-after': '34' },
      }),
    );
    expect(mapped429?.kind).toBe('rate_limited');
    expect(mapped429?.retryAfterSeconds).toBe(34);

    const mapped404 = getAlignmentRequestErrorState(
      new ApiError('gone', {
        status: 404,
        payload: null,
        detail: 'gone',
      }),
    );
    expect(mapped404?.kind).toBe('not_found');

    const mapped401 = getAlignmentRequestErrorState(
      new ApiError('unauthorized', {
        status: 401,
        payload: null,
        detail: 'unauthorized',
      }),
    );
    expect(mapped401?.kind).toBe('auth');

    const mapped429Cooldown = getAlignmentRequestErrorState(
      new ApiError('already run recently', {
        status: 429,
        payload: null,
        detail: 'This document+course alignment check was already run recently',
        headers: { 'retry-after': '12' },
      }),
    );
    expect(mapped429Cooldown?.kind).toBe('duplicate_cooldown');
    expect(mapped429Cooldown?.retryAfterSeconds).toBe(12);
  });
});

describe('coverage and evidence helpers', () => {
  it('renders bounded and legacy coverage banners', () => {
    expect(buildCoverageBanner({
      scope: 'bounded',
      total_pages: 10,
      evaluated_pages: 3,
      total_chars: null,
      evaluated_chars: null,
    }).kind).toBe('bounded');

    expect(
      buildCoverageBanner({
        scope: 'legacy_unknown',
        total_pages: null,
        evaluated_pages: null,
        total_chars: null,
        evaluated_chars: null,
      }).kind,
    ).toBe('legacy');
  });

  it('maps bounded not_addressed to not_observed in derived summary', () => {
    const check = {
      check_id: 'check-1',
      objective_results: [
        {
          code: 'O1',
          description: 'd',
          expected_level: 'D',
          is_addressed: false,
          status: 'not_addressed',
        },
      ],
      summary: {
        total_mapped_objectives: 1,
        match: 0,
        under_developed: 0,
        over_developed: 0,
        not_addressed: 1,
        not_observed: 0,
      },
      coverage: {
        scope: 'bounded',
        total_pages: 10,
        evaluated_pages: 5,
        total_chars: null,
        evaluated_chars: null,
      },
      document_id: 'd',
      course_id: 'c',
      course_title: 'Course',
      run_at: new Date().toISOString(),
      model_name: null,
      success: true,
      error_message: null,
    } as AlignmentCheck;

    const summary = buildDisplayedSummary(check);
    expect(summary.not_observed).toBe(1);
    expect(summary.not_addressed).toBe(0);
  });

  it('builds evidence navigation payload for table click', () => {
    expect(getEvidenceNavigation(4, 'Evidence excerpt')).toEqual({
      pageNumber: 4,
      evidence: 'Evidence excerpt',
    });

    expect(getEvidenceNavigation(null, 'Evidence excerpt')).toBeNull();
  });

  it('renders advisory banner text from coverage provenance fallback', () => {
    const check: AlignmentCheck = {
      check_id: 'check-2',
      document_id: 'doc',
      course_id: 'course',
      course_title: 'Course',
      run_at: new Date().toISOString(),
      model_name: null,
      objective_results: [],
      summary: {
        total_mapped_objectives: 0,
        match: 0,
        under_developed: 0,
        over_developed: 0,
        not_addressed: 0,
      },
      success: true,
      error_message: null,
      provenance: {
        coverage: {
          scope: 'legacy_unknown',
          total_pages: null,
          evaluated_pages: null,
          total_chars: null,
          evaluated_chars: null,
        },
      },
    };

    expect(
      buildCoverageBanner(
        check.provenance?.coverage || {
          scope: 'legacy_unknown',
          total_pages: null,
          evaluated_pages: null,
          total_chars: null,
          evaluated_chars: null,
        },
      ).text,
    ).toBe(
      'Evaluation scope unavailable',
    );
  });

  it('uses provenance coverage when direct coverage field is absent', () => {
    const check: AlignmentCheck = {
      check_id: 'check-3',
      document_id: 'doc',
      course_id: 'course',
      course_title: 'Course',
      run_at: new Date().toISOString(),
      model_name: null,
      objective_results: [],
      summary: {
        total_mapped_objectives: 0,
        match: 0,
        under_developed: 0,
        over_developed: 0,
        not_addressed: 0,
      },
      success: true,
      error_message: null,
      provenance: {
        coverage: {
          scope: 'bounded',
          total_pages: 50,
          evaluated_pages: 12,
          total_chars: null,
          evaluated_chars: null,
        },
      },
    };

    expect(getCoverageMetadata(check).scope).toBe('bounded');
    expect(buildCoverageBanner(getCoverageMetadata(check)).text).toBe('Evaluated pages: 12 / 50');
  });
});
