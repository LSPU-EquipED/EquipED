import { describe, expect, it } from 'vitest';
import { statusBadgeClasses, statusLabel } from '../alignmentHelpers';

describe('statusLabel', () => {
  it('renders a human label for each status', () => {
    expect(statusLabel('match')).toBe('Match');
    expect(statusLabel('under-developed')).toBe('Under-developed');
    expect(statusLabel('over-developed')).toBe('Over-developed');
    expect(statusLabel('not_addressed')).toBe('Not addressed');
    expect(statusLabel('not_observed')).toBe('Not observed in evaluated pages');
  });
});

describe('statusBadgeClasses', () => {
  it('uses green for match', () => {
    expect(statusBadgeClasses('match')).toContain('success');
  });

  it('uses light blue for over-developed', () => {
    expect(statusBadgeClasses('over-developed')).toContain('info');
  });

  it('uses gold for under-developed', () => {
    expect(statusBadgeClasses('under-developed')).toContain('warning');
  });

  it('uses red for not_addressed', () => {
    expect(statusBadgeClasses('not_addressed')).toContain('destructive');
  });
});
