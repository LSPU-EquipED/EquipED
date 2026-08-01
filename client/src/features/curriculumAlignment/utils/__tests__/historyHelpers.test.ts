import { describe, expect, it } from 'vitest';
import { formatSummaryChips } from '../historyHelpers';

describe('formatSummaryChips', () => {
  it('formats all four counts in order, including zeros', () => {
    const summary = {
      total_mapped_objectives: 6,
      match: 2,
      under_developed: 1,
      over_developed: 0,
      not_addressed: 3,
    };
    expect(formatSummaryChips(summary)).toBe('2 match · 1 under · 0 over · 3 not addressed');
  });

  it('handles an all-zero summary', () => {
    const summary = {
      total_mapped_objectives: 0,
      match: 0,
      under_developed: 0,
      over_developed: 0,
      not_addressed: 0,
    };
    expect(formatSummaryChips(summary)).toBe('0 match · 0 under · 0 over · 0 not addressed');
  });
});
