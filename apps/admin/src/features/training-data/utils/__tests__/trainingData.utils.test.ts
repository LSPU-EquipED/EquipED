import { describe, expect, it } from 'vitest';
import {
  compareToLatestJob,
  describeFunnel,
  formatCountdown,
  formatSize,
  formatSkipReason,
  getReadinessTier,
  getReviewerNote,
  RULE_OF_THUMB_NOTE,
  SEEDED_DATA_NOTE,
  shortHash,
  totalSkipped,
} from '../trainingData.utils';

describe('getReadinessTier', () => {
  it('reports no pairs at all', () => {
    expect(getReadinessTier(0, 0).tier).toBe('empty');
  });

  it('warns that nothing can be held out with a single evaluation, even with many pairs', () => {
    expect(getReadinessTier(50, 1).tier).toBe('single-evaluation');
  });

  it('labels fewer than 20 pairs across several evaluations as small', () => {
    expect(getReadinessTier(19, 4).tier).toBe('small');
  });

  it('labels 20 or more pairs across several evaluations as reasonable', () => {
    expect(getReadinessTier(20, 2).tier).toBe('reasonable');
  });

  it('states the rule of thumb once, outside the per-tier messages', () => {
    expect(RULE_OF_THUMB_NOTE.toLowerCase()).toContain('rule of thumb');
    for (const [pairs, evals] of [
      [0, 0],
      [50, 1],
      [19, 4],
      [100, 10],
    ]) {
      expect(getReadinessTier(pairs, evals).message.toLowerCase()).not.toContain('rule of thumb');
    }
  });

  it('never calls the top tier validated or guaranteed', () => {
    const { message } = getReadinessTier(100, 10);
    expect(message.toLowerCase()).not.toMatch(/validated|guarantee|ready/);
  });
});

describe('getReviewerNote', () => {
  it('warns when every correction comes from one reviewer', () => {
    expect(getReviewerNote(1)).toMatch(/one reviewer/i);
  });

  it('stays quiet with several reviewers or none recorded', () => {
    expect(getReviewerNote(2)).toBeNull();
    expect(getReviewerNote(0)).toBeNull();
  });
});

describe('SEEDED_DATA_NOTE', () => {
  it('says seeded test data cannot be told apart in these counts', () => {
    expect(SEEDED_DATA_NOTE).toMatch(/seeded test data/i);
    expect(SEEDED_DATA_NOTE).toMatch(/whole database/i);
  });
});

describe('compareToLatestJob', () => {
  const readiness = { pair_count: 31, pairs_sha256: 'bbb' };

  it('reports no previous job', () => {
    expect(compareToLatestJob(readiness, undefined)).toEqual({
      kind: 'no-jobs',
    });
  });

  it('reports identical when the hash matches the latest job', () => {
    expect(compareToLatestJob(readiness, { pair_count: 31, pairs_sha256: 'bbb' })).toEqual({
      kind: 'identical',
    });
  });

  it('reports the count change when the hash differs', () => {
    expect(compareToLatestJob(readiness, { pair_count: 25, pairs_sha256: 'aaa' })).toEqual({
      kind: 'changed',
      from: 25,
      to: 31,
    });
  });

  it('reports unknown when the latest job has no recorded hash or count', () => {
    expect(compareToLatestJob(readiness, { pair_count: null, pairs_sha256: null })).toEqual({
      kind: 'unknown',
    });
  });
});

describe('skip reason helpers', () => {
  it('labels the known reason and humanizes unknown ones', () => {
    expect(formatSkipReason('no_reviewer_feedback')).toBe('No reviewer feedback');
    expect(formatSkipReason('some_new_reason')).toBe('Some new reason');
  });

  it('sums skipped counts', () => {
    expect(totalSkipped({ a: 2, b: 3 })).toBe(5);
    expect(totalSkipped({})).toBe(0);
  });
});

describe('describeFunnel', () => {
  it('folds a single skip reason into one sentence', () => {
    expect(describeFunnel(25, { no_reviewer_feedback: 7 })).toBe(
      '32 generations examined: 25 became pairs, 7 skipped (no reviewer feedback).',
    );
  });

  it('breaks several skip reasons down by count', () => {
    expect(describeFunnel(10, { no_reviewer_feedback: 5, some_new_reason: 2 })).toBe(
      '17 generations examined: 10 became pairs, 7 skipped (5 no reviewer feedback, 2 some new reason).',
    );
  });

  it('says none were skipped when nothing was', () => {
    expect(describeFunnel(4, {})).toBe('4 generations examined: 4 became pairs, none skipped.');
  });

  it('ignores zero counts and uses the singular for one generation', () => {
    expect(describeFunnel(1, { no_reviewer_feedback: 0 })).toBe(
      '1 generation examined: 1 became pairs, none skipped.',
    );
  });
});

describe('shortHash', () => {
  it('shortens a hash and tolerates missing values', () => {
    expect(shortHash('0123456789abcdef')).toBe('01234567');
    expect(shortHash(null)).toBe('—');
    expect(shortHash(undefined)).toBe('—');
  });
});

describe('formatCountdown', () => {
  it('returns "Expired" when expiration is past or equal to now', () => {
    const now = 1_000_000;
    expect(formatCountdown(new Date(1_000_000).toISOString(), now)).toBe('Expired');
    expect(formatCountdown(new Date(999_999).toISOString(), now)).toBe('Expired');
  });

  it('formats minutes remaining when under 1 hour', () => {
    const now = 1_000_000;
    const expiresAt = new Date(now + 45 * 60 * 1000).toISOString();
    expect(formatCountdown(expiresAt, now)).toBe('45m remaining');
  });

  it('formats hours and minutes remaining when between 1 hour and 24 hours', () => {
    const now = 1_000_000;
    const expiresAt = new Date(now + (2 * 60 + 15) * 60 * 1000).toISOString();
    expect(formatCountdown(expiresAt, now)).toBe('2h 15m remaining');
  });

  it('formats days and hours remaining when 24 hours or more', () => {
    const now = 1_000_000;
    const expiresAt = new Date(now + (3 * 24 + 5) * 60 * 60 * 1000).toISOString();
    expect(formatCountdown(expiresAt, now)).toBe('3d 5h remaining');
  });
});

describe('formatSize', () => {
  it('formats bytes less than 1 MB as KB', () => {
    expect(formatSize(500)).toBe('1 KB');
    expect(formatSize(1024)).toBe('1 KB');
    expect(formatSize(500 * 1024)).toBe('500 KB');
  });

  it('formats bytes between 1 MB and 1024 MB with 1 decimal place', () => {
    expect(formatSize(1024 * 1024)).toBe('1.0 MB');
    expect(formatSize(10.5 * 1024 * 1024)).toBe('10.5 MB');
    expect(formatSize(10.55 * 1024 * 1024)).toBe('10.6 MB');
  });

  it('formats bytes 1024 MB or greater as GB with 2 decimal places', () => {
    expect(formatSize(1024 * 1024 * 1024)).toBe('1.00 GB');
    expect(formatSize(2.567 * 1024 * 1024 * 1024)).toBe('2.57 GB');
  });
});
