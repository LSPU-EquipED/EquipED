import { describe, expect, it } from 'vitest';
import type { ModelValidationCriterionScore, ModelValidationItem } from '../../types';
import { compareChipKey, computePairComparison, decideWinner } from '../compare';

function score(
  agent: string,
  criterion: string,
  expected: number,
  actual: number | null,
): ModelValidationCriterionScore {
  return {
    expected_score_id: `${agent}-${criterion}`,
    agent_id: agent,
    criterion_id: criterion,
    criterion_title: `Title ${criterion}`,
    expected_score: expected,
    actual_score: actual,
    absolute_error: actual == null ? null : Math.abs(actual - expected),
  };
}

function run(scores: ModelValidationCriterionScore[]): ModelValidationItem {
  return { criterion_scores: scores } as unknown as ModelValidationItem;
}

// expected: 3,3,3,3,3 ; base: 3,2,4,1,3 ; adapter: 3,3,4,2,3
// A-01 same (0 vs 0), A-02 closer (1 -> 0), A-03 same (1 vs 1), A-04 closer? see below
const base = run([
  score('sme', 'A-01', 3, 3),
  score('sme', 'A-02', 3, 2),
  score('sme', 'A-03', 3, 4),
  score('sme', 'A-04', 3, 3),
  score('sme', 'A-05', 3, 4),
]);
const adapter = run([
  score('sme', 'A-01', 3, 3),
  score('sme', 'A-02', 3, 3),
  score('sme', 'A-03', 3, 4),
  score('sme', 'A-04', 3, 1),
  score('sme', 'A-05', 3, 4),
]);

describe('computePairComparison', () => {
  it('computes errors, exact matches, closer/same/farther and averages', () => {
    const result = computePairComparison(base, adapter, new Set());
    expect(result.status).toBe('ok');
    // base errors 0,1,1,0,1 = 3/5 ; adapter errors 0,0,1,2,1 = 4/5
    expect(result.baseMeanError).toBeCloseTo(0.6);
    expect(result.adapterMeanError).toBeCloseTo(0.8);
    expect(result.errorVerdict).toBe('farther');
    expect(result.baseExact).toBe(2);
    expect(result.adapterExact).toBe(2);
    expect(result.closerCount).toBe(1); // A-02
    expect(result.fartherCount).toBe(1); // A-04
    expect(result.sameCount).toBe(3);
    expect(result.baseAverage).toBeCloseTo(3.2);
    expect(result.adapterAverage).toBeCloseTo(3.0);
    expect(result.summary).toBe(
      'The adapter got closer to the expected scores on 1 criteria, stayed the same on 3 and moved away on 1.',
    );
    const meanRow = result.rows.find((r) => r.label === 'Mean error vs expected');
    expect(meanRow).toEqual({
      label: 'Mean error vs expected',
      base: '0.60',
      adapter: '0.80',
      result: 'FARTHER',
      better: 'base',
    });
    expect(result.rows.find((r) => r.label === 'Exact matches')).toMatchObject({
      base: '2 of 5',
      adapter: '2 of 5',
      result: '0',
    });
    expect(result.rows.find((r) => r.label === 'Average score')).toMatchObject({
      base: '3.20',
      adapter: '3.00',
      result: '-0.20',
    });
    expect(result.rows.find((r) => r.label === 'Criteria: closer / same / farther')).toMatchObject(
      { result: '1 / 3 / 1' },
    );
  });

  it('reports CLOSER with a plus sign on the exact match difference', () => {
    const better = run([score('sme', 'A-01', 3, 3), score('sme', 'A-02', 3, 3)]);
    const worse = run([score('sme', 'A-01', 3, 3), score('sme', 'A-02', 3, 1)]);
    const result = computePairComparison(worse, better, new Set());
    expect(result.errorVerdict).toBe('closer');
    expect(result.rows[0].result).toBe('CLOSER');
    expect(result.rows.find((r) => r.label === 'Exact matches')?.result).toBe('+1');
  });

  it('skipping a criterion removes it from every number', () => {
    const result = computePairComparison(base, adapter, new Set([compareChipKey('sme', 'A-04')]));
    expect(result.baseMeanError).toBeCloseTo(0.75);
    expect(result.adapterMeanError).toBeCloseTo(0.5);
    expect(result.errorVerdict).toBe('closer');
    expect(result.fartherCount).toBe(0);
    expect(result.closerCount).toBe(1);
    expect(result.sameCount).toBe(3);
    expect(result.rows.find((r) => r.label === 'Exact matches')?.base).toBe('1 of 4');
    expect(result.chips).toHaveLength(5);
    expect(result.chips.find((c) => c.key === compareChipKey('sme', 'A-04'))?.skipped).toBe(true);
  });

  it('ignores criteria missing from one run or with a null actual score', () => {
    const a = run([score('sme', 'A-01', 3, 3), score('sme', 'A-02', 3, null), score('sme', 'A-03', 3, 2)]);
    const b = run([score('sme', 'A-01', 3, 2), score('sme', 'A-02', 3, 3), score('gad', 'G-01', 3, 3)]);
    const result = computePairComparison(a, b, new Set());
    expect(result.chips.map((c) => c.key)).toEqual([compareChipKey('sme', 'A-01')]);
    expect(result.rows.find((r) => r.label === 'Exact matches')?.base).toBe('1 of 1');
  });

  it('matches by agent and criterion together', () => {
    const a = run([score('sme', 'X-01', 3, 3)]);
    const b = run([score('gad', 'X-01', 3, 3)]);
    expect(computePairComparison(a, b, new Set()).status).toBe('no-overlap');
  });

  it('handles no overlap and all skipped without NaN', () => {
    const none = computePairComparison(run([]), run([]), new Set());
    expect(none.status).toBe('no-overlap');
    expect(none.rows).toEqual([]);
    expect(none.summary).toBe('');

    const all = computePairComparison(
      base,
      adapter,
      new Set(['sme:A-01', 'sme:A-02', 'sme:A-03', 'sme:A-04', 'sme:A-05']),
    );
    expect(all.status).toBe('all-skipped');
    expect(all.rows).toEqual([]);
    expect(JSON.stringify(all)).not.toMatch(/NaN|undefined/);
  });
});

describe('decideWinner', () => {
  it('picks the side with the lower mean error', () => {
    expect(decideWinner(1, 0.5, 1, 1)).toBe('adapter');
    expect(decideWinner(0.5, 1, 1, 3)).toBe('base');
  });
  it('breaks an error tie with exact matches', () => {
    expect(decideWinner(1, 1, 2, 3)).toBe('adapter');
    expect(decideWinner(1, 1, 3, 2)).toBe('base');
  });
  it('is a tie when both error and exact matches are equal', () => {
    expect(decideWinner(1, 1, 2, 2)).toBe('tie');
  });
  it('returns null when one side is missing', () => {
    expect(decideWinner(null, 1, 2, 2)).toBeNull();
    expect(decideWinner(1, null, 2, 2)).toBeNull();
  });
});

describe('better markers on rows', () => {
  it('marks mean error (lower) and exact matches (higher), never the average', () => {
    const result = computePairComparison(base, adapter, new Set([compareChipKey('sme', 'A-04')]));
    expect(result.winner).toBe('adapter');
    const by = (label: string) => result.rows.find((r) => r.label === label)?.better;
    expect(by('Mean error vs expected')).toBe('adapter');
    expect(by('Exact matches')).toBe('adapter');
    expect(by('Average score')).toBeNull();
    expect(by('Criteria: closer / same / farther')).toBeNull();
  });
  it('has no winner when nothing is comparable', () => {
    expect(computePairComparison(run([]), run([]), new Set()).winner).toBeNull();
  });
});

describe('shared yardstick', () => {
  it('excludes criteria whose expected scores differ and lists them', () => {
    const a = run([score('sme', 'A-01', 3, 3), score('sme', 'A-05', 3, 3)]);
    const b = run([score('sme', 'A-01', 3, 2), score('sme', 'A-05', 4, 4)]);
    const result = computePairComparison(a, b, new Set());
    expect(result.differingExpected).toEqual(['A-05']);
    expect(result.chips.map((c) => c.key)).toEqual([compareChipKey('sme', 'A-01')]);
    expect(result.rows.find((r) => r.label === 'Exact matches')?.base).toBe('1 of 1');
    expect(result.baseMeanError).toBe(0);
    expect(result.adapterMeanError).toBe(1);
  });

  it('excludes criteria with a non-numeric expected score on either side', () => {
    const bad = (v: unknown) =>
      ({ ...score('sme', 'A-02', 3, 3), expected_score: v }) as unknown as ModelValidationCriterionScore;
    const a = run([score('sme', 'A-01', 3, 3), bad(null)]);
    const b = run([score('sme', 'A-01', 3, 3), score('sme', 'A-02', 3, 3)]);
    expect(computePairComparison(a, b, new Set()).chips).toHaveLength(1);
    expect(computePairComparison(b, a, new Set()).chips).toHaveLength(1);
  });

  it('reports no-overlap with the differing list when every criterion differs', () => {
    const a = run([score('sme', 'A-05', 3, 3)]);
    const b = run([score('sme', 'A-05', 2, 3)]);
    const result = computePairComparison(a, b, new Set());
    expect(result.status).toBe('no-overlap');
    expect(result.differingExpected).toEqual(['A-05']);
  });

  it('treats errors equal at 2 decimals as a tie', () => {
    expect(decideWinner(0.4, 0.40004, 1, 1)).toBe('tie');
    expect(decideWinner(0.4, 0.40004, 1, 2)).toBe('adapter');
  });
});
