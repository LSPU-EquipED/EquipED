import { describe, expect, it } from 'vitest';
import {
  formatDate,
  healthBadgeClass,
  isPolicyArea,
  processingStatusClass,
  referenceTypeLabels,
} from '../helpers';

describe('isPolicyArea', () => {
  it('identifies valid policy areas', () => {
    expect(isPolicyArea('data_privacy')).toBe(true);
    expect(isPolicyArea('intellectual_property')).toBe(true);
    expect(isPolicyArea('invalid')).toBe(false);
    expect(isPolicyArea(null)).toBe(false);
  });
});

describe('processingStatusClass', () => {
  it('returns correct class for statuses', () => {
    expect(processingStatusClass('PROCESSED')).toContain('bg-success');
    expect(processingStatusClass('FAILED')).toContain('bg-destructive');
    expect(processingStatusClass('PENDING')).toContain('bg-warning');
  });
});

describe('healthBadgeClass', () => {
  it('returns green for healthy and red for unhealthy', () => {
    expect(healthBadgeClass(true)).toContain('text-success');
    expect(healthBadgeClass(false)).toContain('text-destructive');
  });
});

describe('formatDate', () => {
  it('formats valid iso string', () => {
    expect(formatDate('2026-07-30T00:00:00Z')).not.toBe('2026-07-30T00:00:00Z');
  });

  it('returns original input when date is invalid', () => {
    expect(formatDate('invalid')).toBe('invalid');
  });
});

describe('referenceTypeLabels', () => {
  it('maps curriculum and syllabus to proper labels', () => {
    expect(referenceTypeLabels.curriculum).toBe('Curriculum');
    expect(referenceTypeLabels.syllabus).toBe('Syllabus');
  });
});
