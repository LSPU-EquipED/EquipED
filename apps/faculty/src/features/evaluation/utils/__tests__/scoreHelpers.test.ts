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
  sortCriteriaGrouped,
  getAdjectivalRatingClasses,
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

describe('getAdjectivalRatingClasses', () => {
  it('returns canonical style classes across rating buckets', () => {
    expect(getAdjectivalRatingClasses('Very Satisfactory')).toBe(
      'bg-success-soft text-success border-success/30',
    );
    expect(getAdjectivalRatingClasses('Satisfactory')).toBe(
      'bg-info-soft text-info border-info/30',
    );
    expect(getAdjectivalRatingClasses('Needs Improvement')).toBe(
      'bg-warning-soft text-warning border-warning/30',
    );
    expect(getAdjectivalRatingClasses('Poor')).toBe(
      'bg-destructive-soft text-destructive border-destructive/30',
    );
    expect(getAdjectivalRatingClasses('Unsatisfactory')).toBe(
      'bg-destructive-soft text-destructive border-destructive/30',
    );
    expect(getAdjectivalRatingClasses(undefined)).toBe(
      'bg-surface-subtle text-text-muted border-border',
    );
    expect(getAdjectivalRatingClasses('Unknown')).toBe(
      'bg-surface-subtle text-text-muted border-border',
    );
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

describe('sortCriteriaGrouped', () => {
  it('groups criteria by domain/category instead of alternating by display_order', () => {
    // Alternating input (e.g. OP-01, A-01, OP-02, A-02) with identical display_order numbers
    const alternating = [
      { criterion_id: 'OP-01', criterion_text: 'Topic Coherence', display_order: 1, score: 4, justification: '' },
      { criterion_id: 'A-01', criterion_text: 'Learner Transformation', display_order: 1, score: 3, justification: '' },
      { criterion_id: 'OP-02', criterion_text: 'Interactivity', display_order: 2, score: 4, justification: '' },
      { criterion_id: 'A-02', criterion_text: 'Varied Assessment Tools', display_order: 2, score: 3, justification: '' },
      { criterion_id: 'OP-03', criterion_text: 'Clear Directions', display_order: 3, score: 4, justification: '' },
      { criterion_id: 'A-03', criterion_text: 'Progress Monitoring', display_order: 3, score: 2, justification: '' },
    ];

    const grouped = sortCriteriaGrouped(alternating);
    expect(grouped.map((c) => c.criterion_id)).toEqual([
      'OP-01',
      'OP-02',
      'OP-03',
      'A-01',
      'A-02',
      'A-03',
    ]);
  });

  it('uses form snapshot presentation domain hierarchy when available', () => {
    const criteria = [
      { criterion_id: 'A-02', criterion_text: 'Varied Assessment', display_order: 2, score: 3, justification: '' },
      { criterion_id: 'OP-01', criterion_text: 'Topic Coherence', display_order: 1, score: 4, justification: '' },
      { criterion_id: 'A-01', criterion_text: 'Transformation', display_order: 1, score: 4, justification: '' },
      { criterion_id: 'OP-02', criterion_text: 'Interactivity', display_order: 2, score: 3, justification: '' },
    ];

    const formPresentation = {
      form_snapshot_id: 'snap-1',
      rubric_set_id: 'rubric-1',
      version: 1,
      snapshot_hash: 'hash-1',
      adapter_key: 'sme_adapter',
      adapter_version: 1,
      domains: [
        {
          rubric_domain_id: 'dom-op',
          code: 'OP',
          title: 'Organization & Presentation',
          display_order: 1,
          criteria: [
            { rubric_criterion_id: 'c-op-1', criterion_code: 'OP-01', title: 'Topic Coherence', description: '', display_order: 1 },
            { rubric_criterion_id: 'c-op-2', criterion_code: 'OP-02', title: 'Interactivity', description: '', display_order: 2 },
          ],
        },
        {
          rubric_domain_id: 'dom-a',
          code: 'A',
          title: 'Assessment',
          display_order: 2,
          criteria: [
            { rubric_criterion_id: 'c-a-1', criterion_code: 'A-01', title: 'Transformation', description: '', display_order: 1 },
            { rubric_criterion_id: 'c-a-2', criterion_code: 'A-02', title: 'Varied Assessment', description: '', display_order: 2 },
          ],
        },
      ],
    };

    const grouped = sortCriteriaGrouped(criteria, formPresentation);
    expect(grouped.map((c) => c.criterion_id)).toEqual([
      'OP-01',
      'OP-02',
      'A-01',
      'A-02',
    ]);
  });

  it('handles empty or single item arrays gracefully', () => {
    expect(sortCriteriaGrouped([])).toEqual([]);
    const single = [{ criterion_id: 'OP-01', criterion_text: 'Test', score: 4, justification: '' }];
    expect(sortCriteriaGrouped(single)).toEqual(single);
  });
});
