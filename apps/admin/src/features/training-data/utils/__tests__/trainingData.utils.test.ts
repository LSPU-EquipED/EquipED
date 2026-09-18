import { describe, expect, it } from 'vitest';
import { formatCountdown, formatSize } from '../trainingData.utils';

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
