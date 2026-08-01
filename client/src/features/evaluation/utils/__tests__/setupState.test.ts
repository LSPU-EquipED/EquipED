import { describe, expect, it } from 'vitest';
import type { EvaluationListItem } from '../../types';
import {
  canStartConfirmedPartial,
  normalizeProgram,
  resolveExistingEvaluation,
} from '../setupState';

type ResolveItem = Pick<EvaluationListItem, 'evaluation_id' | 'status' | 'submitted_at'>;

describe('normalizeProgram', () => {
  it('uppercases and trims program codes', () => {
    expect(normalizeProgram('  bscs ')).toBe('BSCS');
  });
});

describe('canStartConfirmedPartial', () => {
  it('requires the program to be explicitly confirmed', () => {
    expect(
      canStartConfirmedPartial({
        program: 'BSCS',
        programConfirmed: false,
        partialAcknowledged: true,
        isSubmitting: false,
      }),
    ).toBe(false);
  });

  it('requires the partial review to be acknowledged', () => {
    expect(
      canStartConfirmedPartial({
        program: 'BSCS',
        programConfirmed: true,
        partialAcknowledged: false,
        isSubmitting: false,
      }),
    ).toBe(false);
  });

  it('allows start only after confirmation and acknowledgement', () => {
    expect(
      canStartConfirmedPartial({
        program: 'BSCS',
        programConfirmed: true,
        partialAcknowledged: true,
        isSubmitting: false,
      }),
    ).toBe(true);
  });

  it('blocks start without a selected program (detected suggestion is not enough)', () => {
    expect(
      canStartConfirmedPartial({
        program: '',
        programConfirmed: true,
        partialAcknowledged: true,
        isSubmitting: false,
      }),
    ).toBe(false);
  });

  it('blocks start while a submission is already pending', () => {
    expect(
      canStartConfirmedPartial({
        program: 'BSCS',
        programConfirmed: true,
        partialAcknowledged: true,
        isSubmitting: true,
      }),
    ).toBe(false);
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
