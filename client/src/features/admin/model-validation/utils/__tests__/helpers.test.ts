import { describe, expect, it } from 'vitest';
import { formatTimestamp, groupCriteriaByAgent } from '../helpers';
import type { ModelValidationCriterionScore } from '../../types';

describe('groupCriteriaByAgent', () => {
  it('groups criteria by agent id in standard agent order', () => {
    const scores: ModelValidationCriterionScore[] = [
      {
        expected_score_id: '1',
        agent_id: 'itso',
        criterion_id: 'ITSO_1',
        criterion_title: 'ITSO Criterion 1',
        expected_score: 4,
        actual_score: 4,
        absolute_error: 0,
      },
      {
        expected_score_id: '2',
        agent_id: 'sme',
        criterion_id: 'SME_1',
        criterion_title: 'SME Criterion 1',
        expected_score: 3,
        actual_score: 3,
        absolute_error: 0,
      },
    ];

    const grouped = groupCriteriaByAgent(scores);
    expect(grouped).toHaveLength(2);
    expect(grouped[0]?.agentId).toBe('sme');
    expect(grouped[1]?.agentId).toBe('itso');
  });

  it('returns empty array when input scores are empty', () => {
    expect(groupCriteriaByAgent([])).toEqual([]);
  });
});

describe('formatTimestamp', () => {
  it('returns dash for null or invalid date', () => {
    expect(formatTimestamp(null)).toBe('—');
    expect(formatTimestamp(undefined)).toBe('—');
    expect(formatTimestamp('invalid-date')).toBe('—');
  });

  it('formats valid ISO date string', () => {
    const formatted = formatTimestamp('2026-07-30T10:00:00Z');
    expect(formatted).not.toBe('—');
    expect(typeof formatted).toBe('string');
  });
});
