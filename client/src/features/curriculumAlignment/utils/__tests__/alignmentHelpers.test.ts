import { describe, expect, it } from 'vitest';
import { statusBadgeClasses, statusLabel } from '../alignmentHelpers';

describe('statusLabel', () => {
  it('renders a human label for each status', () => {
    expect(statusLabel('match')).toBe('Match');
    expect(statusLabel('under-developed')).toBe('Under-developed');
    expect(statusLabel('over-developed')).toBe('Over-developed');
    expect(statusLabel('not_addressed')).toBe('Not addressed');
  });
});

describe('statusBadgeClasses', () => {
  it('uses green for match', () => {
    expect(statusBadgeClasses('match')).toContain('#3b963e');
  });

  it('uses light blue for over-developed', () => {
    expect(statusBadgeClasses('over-developed')).toContain('#3eaed4');
  });

  it('uses gold for under-developed', () => {
    expect(statusBadgeClasses('under-developed')).toContain('#f2c811');
  });

  it('uses red for not_addressed', () => {
    expect(statusBadgeClasses('not_addressed')).toContain('#b91c1c');
  });
});
