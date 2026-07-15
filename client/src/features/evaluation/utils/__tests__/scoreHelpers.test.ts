// Unit tests for the canonical score / formatting helpers. These are
// the source of truth for the on-screen scorecard, the consolidated PDF,
// and the per-agent PDF, so they must match the server's
// `score_to_adjectival` thresholds exactly.
import { describe, expect, it } from 'vitest';
import {
  CANONICAL_MAX_SCORE,
  adjectivalRating,
  agentDisplayLabel,
  agentShortLabel,
  boundNarrative,
  cleanJustification,
  formatCanonicalScore,
  formatMonitoringPercent,
  formatPercentValue,
  formatScore,
  monitoringPercentage,
  overallScoreDisplay,
  scoreTier,
} from '../scoreHelpers';

describe('formatScore', () => {
  it('renders whole numbers without trailing zeros', () => {
    expect(formatScore(3)).toBe('3');
    expect(formatScore(0)).toBe('0');
  });

  it('keeps two decimal places when needed', () => {
    expect(formatScore(3.5)).toBe('3.50');
    expect(formatScore(2.49)).toBe('2.49');
  });

  it('falls back to a dash for non-finite values', () => {
    expect(formatScore(Number.NaN)).toBe('-');
    expect(formatScore(Number.POSITIVE_INFINITY)).toBe('-');
  });
});

describe('adjectivalRating (canonical 1-4 buckets)', () => {
  it('matches the server thresholds exactly', () => {
    expect(adjectivalRating(4.0)).toBe('Very Satisfactory');
    expect(adjectivalRating(3.5)).toBe('Very Satisfactory');
    expect(adjectivalRating(3.49)).toBe('Satisfactory');
    expect(adjectivalRating(2.5)).toBe('Satisfactory');
    expect(adjectivalRating(2.49)).toBe('Needs Improvement');
    expect(adjectivalRating(1.5)).toBe('Needs Improvement');
    expect(adjectivalRating(1.49)).toBe('Poor');
    expect(adjectivalRating(1.0)).toBe('Poor');
  });

  it('reports "Not available" for missing or non-finite values', () => {
    expect(adjectivalRating(null)).toBe('Not available');
    expect(adjectivalRating(undefined)).toBe('Not available');
    expect(adjectivalRating(Number.NaN)).toBe('Not available');
  });
});

describe('monitoringPercentage', () => {
  it('scales 1-4 values to a 0-100 percentage', () => {
    expect(monitoringPercentage(4, 4)).toBe(100);
    expect(monitoringPercentage(3.5, 4)).toBe(88);
    expect(monitoringPercentage(2, 4)).toBe(50);
    expect(monitoringPercentage(0, 4)).toBe(0);
  });

  it('uses the provided maxScore as the denominator', () => {
    // Defensive: if the server ever returns a different max, we still
    // scale to 0-100.
    expect(monitoringPercentage(2, 5)).toBe(40);
  });

  it('returns 0 for invalid denominators or non-numeric subtotals', () => {
    expect(monitoringPercentage(Number.NaN, 4)).toBe(0);
    expect(monitoringPercentage(2, 0)).toBe(0);
    expect(monitoringPercentage(2, -1)).toBe(0);
  });
});

describe('formatCanonicalScore and formatMonitoringPercent', () => {
  it('keeps the 1-4 and 0-100 scales in separate, well-labeled strings', () => {
    expect(formatCanonicalScore(3.5)).toBe('3.50/4');
    expect(formatMonitoringPercent(3.5, 4)).toBe('88%');
  });

  it('falls back gracefully when a value is missing', () => {
    expect(formatCanonicalScore(null)).toBe('—');
    expect(formatMonitoringPercent(NaN, 4)).toBe('0%');
  });
});

describe('formatPercentValue (server-provided 0-100 values)', () => {
  it('appends a % suffix to numeric values', () => {
    expect(formatPercentValue(86)).toBe('86%');
    expect(formatPercentValue(86.5)).toBe('86.50%');
    expect(formatPercentValue(0)).toBe('0%');
  });

  it('returns an em-dash for missing or non-finite values', () => {
    expect(formatPercentValue(null)).toBe('—');
    expect(formatPercentValue(undefined)).toBe('—');
    expect(formatPercentValue(Number.NaN)).toBe('—');
  });
});

describe('overallScoreDisplay', () => {
  // Regression: Scorecard.tsx used to render `synthesized_score` (a
  // server-computed 0-100 percentage) with a `/4` suffix, which is
  // nonsense. The display helper must always pair the canonical 1-4
  // value with a `/4` label and the monitoring value with a `%` label.
  it('renders overall_score as `<n>/4` and never as a percentage', () => {
    const display = overallScoreDisplay({
      overallScore: 3.5,
      synthesizedScore: 87.5,
    });
    expect(display.hasCanonical).toBe(true);
    expect(display.canonicalText).toBe('3.50/4');
    expect(display.canonicalText).not.toMatch(/%/);
    // The monitoring value is recomputed from the canonical score so
    // the two displays stay consistent.
    expect(display.monitoringText).toBe('88%');
  });

  it('falls back to the server percentage only when no canonical score is available', () => {
    const display = overallScoreDisplay({
      overallScore: null,
      synthesizedScore: 87.5,
    });
    expect(display.hasCanonical).toBe(false);
    expect(display.canonicalText).toBe('—');
    expect(display.monitoringText).toBe('87.50%');
  });

  it('reports an em-dash for monitoring when both fields are missing', () => {
    const display = overallScoreDisplay({});
    expect(display.canonicalText).toBe('—');
    expect(display.monitoringText).toBe('—');
    expect(display.hasCanonical).toBe(false);
  });

  it('treats a 0-100 server percentage as unavailable for the /4 slot', () => {
    // This is the exact scenario the council flagged: if a future
    // caller hands us only `synthesized_score`, we must not pretend
    // it is a 1-4 score.
    const display = overallScoreDisplay({ synthesizedScore: 86.0 });
    expect(display.canonicalText).toBe('—');
    expect(display.monitoringText).toBe('86%');
  });

  it('ignores a non-finite canonical score and falls back gracefully', () => {
    const display = overallScoreDisplay({
      overallScore: Number.NaN,
      synthesizedScore: 75,
    });
    expect(display.hasCanonical).toBe(false);
    expect(display.canonicalText).toBe('—');
    expect(display.monitoringText).toBe('75%');
  });
});

describe('cleanJustification (chunk_id sanitization)', () => {
  it('strips raw chunk_id tokens in both quoted and bare forms', () => {
    expect(cleanJustification('Good content chunk_id "abc-123" overall.')).toBe(
      'Good content overall.',
    );
    expect(cleanJustification('See chunk_id xyz-9 for evidence.')).toBe('See for evidence.');
  });

  it('strips bracket and parenthetical chunk_id references', () => {
    expect(cleanJustification('Content [chunk_id: foo-1] verified.')).toBe('Content verified.');
    expect(cleanJustification('Content (chunk_id=bar-2) verified.')).toBe('Content verified.');
  });

  it('collapses extra whitespace left behind', () => {
    expect(cleanJustification('Hello   world  .')).toBe('Hello world.');
  });

  it('returns an empty string for missing input', () => {
    expect(cleanJustification('')).toBe('');
    expect(cleanJustification(null)).toBe('');
    expect(cleanJustification(undefined)).toBe('');
  });
});

describe('boundNarrative', () => {
  it('passes short text through after cleaning', () => {
    expect(boundNarrative('Good coverage of the topic.', 100)).toBe('Good coverage of the topic.');
  });

  it('truncates at a word boundary and appends an ellipsis', () => {
    const long = 'one two three four five six seven eight nine ten';
    const out = boundNarrative(long, 18);
    expect(out.endsWith('…')).toBe(true);
    expect(out.length).toBeLessThanOrEqual(20);
    expect(out).not.toContain('nine');
  });

  it('removes chunk_id tokens inside long narratives before bounding', () => {
    const out = boundNarrative(
      'alpha beta gamma delta epsilon chunk_id "abc" zeta eta theta',
      60,
    );
    expect(out).not.toContain('chunk_id');
    expect(out).not.toContain('abc');
  });
});

describe('agentDisplayLabel / agentShortLabel', () => {
  it('returns canonical English labels for known agents', () => {
    expect(agentDisplayLabel('sme')).toContain('Subject Matter Expert');
    expect(agentDisplayLabel('coordinator')).toContain('Program Coordinator');
    expect(agentDisplayLabel('gad')).toContain('Gender and Development');
    expect(agentDisplayLabel('itso')).toContain('Innovation and Technology');
  });

  it('returns short labels without hard-coding case', () => {
    expect(agentShortLabel('SME')).toBe('SME');
    expect(agentShortLabel('GAD')).toBe('GAD');
  });

  it('falls back to upper-cased agent id for unknown agents', () => {
    expect(agentDisplayLabel('reviewer')).toBe('REVIEWER');
    expect(agentShortLabel(null)).toBe('AGENT');
  });
});

describe('scoreTier', () => {
  it('maps canonical 1-4 scores to UI tiers', () => {
    expect(scoreTier(4)).toBe('strong');
    expect(scoreTier(3)).toBe('strong');
    expect(scoreTier(2.99)).toBe('moderate');
    expect(scoreTier(2)).toBe('moderate');
    expect(scoreTier(1.99)).toBe('weak');
    expect(scoreTier(1)).toBe('weak');
  });

  it('returns unknown for missing or non-finite values', () => {
    expect(scoreTier(null)).toBe('unknown');
    expect(scoreTier(Number.NaN)).toBe('unknown');
  });
});

describe('CANONICAL_MAX_SCORE', () => {
  it('is fixed at 4', () => {
    expect(CANONICAL_MAX_SCORE).toBe(4);
  });
});
