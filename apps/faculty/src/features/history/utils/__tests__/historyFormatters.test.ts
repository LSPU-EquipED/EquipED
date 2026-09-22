import { describe, expect, it } from 'vitest';
import {
  formatDate,
  formatDuration,
  formatRelativeTime,
  getStatusVariant,
} from '../historyFormatters';

describe('historyFormatters', () => {
  describe('getStatusVariant', () => {
    it('returns destructive for FAILED and ERROR', () => {
      expect(getStatusVariant('FAILED')).toBe('destructive');
      expect(getStatusVariant('error')).toBe('destructive');
    });

    it('returns success for COMPLETED status', () => {
      expect(getStatusVariant('COMPLETED')).toBe('success');
      expect(getStatusVariant('completed_with_warnings')).toBe('success');
    });

    it('returns info for in-progress states', () => {
      expect(getStatusVariant('EVALUATING')).toBe('info');
      expect(getStatusVariant('PREPROCESSING')).toBe('info');
      expect(getStatusVariant('SYNTHESIZING')).toBe('info');
      expect(getStatusVariant('PROCESSING')).toBe('info');
    });

    it('returns warning for queued states', () => {
      expect(getStatusVariant('SUBMITTED')).toBe('warning');
      expect(getStatusVariant('PENDING')).toBe('warning');
      expect(getStatusVariant('QUEUED')).toBe('warning');
    });

    it('returns neutral for unknown states', () => {
      expect(getStatusVariant('UNKNOWN')).toBe('neutral');
    });
  });

  describe('formatDate', () => {
    it('formats an ISO date string properly', () => {
      const formatted = formatDate('2026-08-20T10:00:00Z');
      expect(formatted).toContain('2026');
      expect(formatted).toContain('Aug');
    });

    it('returns empty string for invalid date', () => {
      expect(formatDate('invalid-date')).toBe('');
    });
  });

  describe('formatDuration', () => {
    it('formats seconds when provided directly', () => {
      expect(formatDuration(45)).toBe('45s');
      expect(formatDuration(125)).toBe('2m 5s');
    });

    it('calculates duration from timestamps when seconds is omitted', () => {
      const duration = formatDuration(
        undefined,
        '2026-08-20T10:00:00Z',
        '2026-08-20T10:02:15Z',
      );
      expect(duration).toBe('2m 15s');
    });

    it('returns null when duration cannot be calculated', () => {
      expect(formatDuration(undefined, undefined, undefined)).toBeNull();
    });
  });

  describe('formatRelativeTime', () => {
    it('formats relative times gracefully', () => {
      const now = new Date();
      expect(formatRelativeTime(now.toISOString())).toBe('just now');

      const pastTenMins = new Date(now.getTime() - 10 * 60 * 1000);
      expect(formatRelativeTime(pastTenMins.toISOString())).toBe('10m ago');

      const pastTwoHours = new Date(now.getTime() - 2 * 60 * 60 * 1000);
      expect(formatRelativeTime(pastTwoHours.toISOString())).toBe('2h ago');
    });

    it('returns empty string on parse error', () => {
      expect(formatRelativeTime('invalid')).toBe('');
    });
  });
});
