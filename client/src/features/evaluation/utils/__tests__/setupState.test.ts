import { describe, expect, it } from 'vitest';
import type { EvaluationListItem } from '../../types';
import {
  buildEvaluationSubmitPayload,
  canStartEvaluation,
  normalizeProgram,
  resolveExistingEvaluation,
} from '../setupState';

type ResolveItem = Pick<EvaluationListItem, 'evaluation_id' | 'status' | 'submitted_at'>;

describe('normalizeProgram - Canonical Constant Normalization', () => {
  it('canonicalizes BSCS variants to exact BSCS', () => {
    expect(normalizeProgram('BSCS')).toBe('BSCS');
    expect(normalizeProgram('  bscs ')).toBe('BSCS');
  });

  it('canonicalizes BSInfoTech, BSINFOTECH, BSIT, and bsit to exact canonical BSInfoTech', () => {
    expect(normalizeProgram('BSInfoTech')).toBe('BSInfoTech');
    expect(normalizeProgram('BSINFOTECH')).toBe('BSInfoTech');
    expect(normalizeProgram('bsinfotech')).toBe('BSInfoTech');
    expect(normalizeProgram('BSIT')).toBe('BSInfoTech');
    expect(normalizeProgram('  bsit  ')).toBe('BSInfoTech');
  });

  it('preserves other trimmed program strings', () => {
    expect(normalizeProgram('  BSIS  ')).toBe('BSIS');
  });
});

describe('canStartEvaluation - Pure Decision Gates', () => {
  describe('Full Evaluation Mode', () => {
    it('allows start when program is confirmed and a ready curriculum is explicitly selected', () => {
      expect(
        canStartEvaluation({
          program: 'BSInfoTech',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: 'curr-123',
          readyCurriculumIds: ['curr-123', 'curr-456'],
          isSubmitting: false,
        }),
      ).toBe(true);
    });

    it('blocks start when selected curriculum ID is not in readyCurriculumIds', () => {
      expect(
        canStartEvaluation({
          program: 'BSInfoTech',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: 'curr-stale-999',
          readyCurriculumIds: ['curr-123', 'curr-456'],
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start when curriculum is not selected (no auto-selection allowed)', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: null,
          isSubmitting: false,
        }),
      ).toBe(false);

      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: '',
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start when program is not confirmed even if curriculum is selected', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: false,
          mode: 'full',
          selectedCurriculumId: 'curr-123',
          readyCurriculumIds: ['curr-123'],
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start when program is an unsupported non-empty string (e.g. BSIS)', () => {
      expect(
        canStartEvaluation({
          program: 'BSIS',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: 'curr-123',
          readyCurriculumIds: ['curr-123'],
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('allows start when program is a supported alias like BSIT', () => {
      expect(
        canStartEvaluation({
          program: 'BSIT',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: 'curr-123',
          readyCurriculumIds: ['curr-123'],
          isSubmitting: false,
        }),
      ).toBe(true);
    });

    it('blocks start when curricula suggestions are currently loading', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: 'curr-123',
          readyCurriculumIds: ['curr-123'],
          isLoadingCurricula: true,
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start when curricula suggestions resulted in an error', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: 'curr-123',
          readyCurriculumIds: ['curr-123'],
          isCurriculaError: true,
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start when existing evaluation resolver resulted in an error', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: 'curr-123',
          readyCurriculumIds: ['curr-123'],
          isResolveError: true,
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start while submission is pending', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: true,
          mode: 'full',
          selectedCurriculumId: 'curr-123',
          readyCurriculumIds: ['curr-123'],
          isSubmitting: true,
        }),
      ).toBe(false);
    });
  });

  describe('Partial Evaluation Mode', () => {
    it('allows start when program is confirmed and partial terms are acknowledged', () => {
      expect(
        canStartEvaluation({
          program: 'BSInfoTech',
          programConfirmed: true,
          mode: 'partial',
          partialAcknowledged: true,
          isSubmitting: false,
        }),
      ).toBe(true);
    });

    it('blocks start when partial terms are not acknowledged', () => {
      expect(
        canStartEvaluation({
          program: 'BSInfoTech',
          programConfirmed: true,
          mode: 'partial',
          partialAcknowledged: false,
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start when resolver resulted in an error', () => {
      expect(
        canStartEvaluation({
          program: 'BSInfoTech',
          programConfirmed: true,
          mode: 'partial',
          partialAcknowledged: true,
          isResolveError: true,
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start when program is not confirmed even if partial is acknowledged', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: false,
          mode: 'partial',
          partialAcknowledged: true,
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start when program is an unsupported non-empty string (e.g. BSIS)', () => {
      expect(
        canStartEvaluation({
          program: 'BSIS',
          programConfirmed: true,
          mode: 'partial',
          partialAcknowledged: true,
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('allows start when program is a supported alias like BSIT', () => {
      expect(
        canStartEvaluation({
          program: 'BSIT',
          programConfirmed: true,
          mode: 'partial',
          partialAcknowledged: true,
          isSubmitting: false,
        }),
      ).toBe(true);
    });

    it('blocks start when program is empty', () => {
      expect(
        canStartEvaluation({
          program: '',
          programConfirmed: true,
          mode: 'partial',
          partialAcknowledged: true,
          isSubmitting: false,
        }),
      ).toBe(false);
    });

    it('blocks start while submission is pending', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: true,
          mode: 'partial',
          partialAcknowledged: true,
          isSubmitting: true,
        }),
      ).toBe(false);
    });
  });

  describe('Unselected / Null Mode', () => {
    it('blocks start when no mode has been selected', () => {
      expect(
        canStartEvaluation({
          program: 'BSCS',
          programConfirmed: true,
          mode: null,
          selectedCurriculumId: 'curr-123',
          partialAcknowledged: true,
          isSubmitting: false,
        }),
      ).toBe(false);
    });
  });
});

describe('buildEvaluationSubmitPayload - Exact Payload Generation & Canonical Constants', () => {
  it('builds exact full evaluation payload for BSCS', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-abc-123',
      program: '  bscs  ',
      mode: 'full',
      curriculumId: 'curr-xyz-789',
    });

    expect(payload).toEqual({
      document_id: 'doc-abc-123',
      curriculum_id: 'curr-xyz-789',
      confirmed_program: 'BSCS',
      partial_without_curriculum: false,
    });
  });

  it('builds exact full evaluation payload for BSInfoTech (never uppercase BSINFOTECH)', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-abc-123',
      program: 'bsinfotech',
      mode: 'full',
      curriculumId: 'curr-it-001',
    });

    expect(payload).toEqual({
      document_id: 'doc-abc-123',
      curriculum_id: 'curr-it-001',
      confirmed_program: 'BSInfoTech',
      partial_without_curriculum: false,
    });
  });

  it('builds exact full evaluation payload for BSIT alias (canonicalized to BSInfoTech)', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-abc-123',
      program: 'BSIT',
      mode: 'full',
      curriculumId: 'curr-it-001',
    });

    expect(payload).toEqual({
      document_id: 'doc-abc-123',
      curriculum_id: 'curr-it-001',
      confirmed_program: 'BSInfoTech',
      partial_without_curriculum: false,
    });
  });

  it('rejects unsupported programs on full evaluation write', () => {
    expect(() =>
      buildEvaluationSubmitPayload({
        documentId: 'doc-abc-123',
        program: 'BSIS',
        mode: 'full',
        curriculumId: 'curr-123',
      }),
    ).toThrow(/Invalid program 'BSIS'/);
  });

  it('rejects unsupported programs on partial evaluation write', () => {
    expect(() =>
      buildEvaluationSubmitPayload({
        documentId: 'doc-abc-123',
        program: 'BSIS',
        mode: 'partial',
      }),
    ).toThrow(/Invalid program 'BSIS'/);
  });

  it('rejects empty program string on payload build', () => {
    expect(() =>
      buildEvaluationSubmitPayload({
        documentId: 'doc-abc-123',
        program: '',
        mode: 'partial',
      }),
    ).toThrow(/Invalid program ''/);
  });

  it('builds exact partial evaluation payload for BSInfoTech (never uppercase BSINFOTECH)', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-abc-123',
      program: 'BSIT',
      mode: 'partial',
    });

    expect(payload).toEqual({
      document_id: 'doc-abc-123',
      confirmed_program: 'BSInfoTech',
      partial_without_curriculum: true,
    });
  });

  it('builds exact partial evaluation payload for BSCS', () => {
    const payload = buildEvaluationSubmitPayload({
      documentId: 'doc-abc-123',
      program: 'BSCS',
      mode: 'partial',
    });

    expect(payload).toEqual({
      document_id: 'doc-abc-123',
      confirmed_program: 'BSCS',
      partial_without_curriculum: true,
    });
  });

  it('throws an error if full evaluation mode is requested without a curriculumId', () => {
    expect(() =>
      buildEvaluationSubmitPayload({
        documentId: 'doc-abc-123',
        program: 'BSCS',
        mode: 'full',
        curriculumId: null,
      }),
    ).toThrow('Curriculum ID is required for full evaluation');
  });
});

describe('resolveExistingEvaluation', () => {
  const baseItems: ResolveItem[] = [
    {
      evaluation_id: 'failed-old',
      status: 'FAILED',
      submitted_at: '2026-01-02T00:00:00Z',
    },
    {
      evaluation_id: 'completed',
      status: 'COMPLETED',
      submitted_at: '2026-01-01T00:00:00Z',
    },
  ];

  it('reuses the most recent non-failed evaluation', () => {
    expect(
      resolveExistingEvaluation([
        ...baseItems,
        {
          evaluation_id: 'running-new',
          status: 'EVALUATING',
          submitted_at: '2026-01-03T00:00:00Z',
        },
      ]),
    ).toBe('running-new');
  });

  it('falls back to an older completed evaluation when the newest failed', () => {
    expect(resolveExistingEvaluation(baseItems)).toBe('completed');
  });

  it('returns null when only failed evaluations exist', () => {
    expect(resolveExistingEvaluation([baseItems[0]])).toBeNull();
  });

  it('returns null when no evaluations exist', () => {
    expect(resolveExistingEvaluation([])).toBeNull();
  });
});
