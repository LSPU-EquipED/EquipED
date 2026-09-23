import { describe, expect, it } from 'vitest';
import { normalizeUserEmail, validateUserEmail } from '../userEmail';

describe('validateUserEmail', () => {
  it('maps required error message for blank inputs', () => {
    expect(validateUserEmail('')).toBe('Email is required.');
    expect(validateUserEmail(undefined)).toBe('Email is required.');
    expect(validateUserEmail(null)).toBe('Email is required.');
  });

  it('maps max length error message when trimmed input exceeds 40 characters', () => {
    const longEmail = `${'a'.repeat(30)}@lspu.edu.ph`;
    expect(validateUserEmail(longEmail)).toBe('Email must be 40 characters or fewer.');
  });

  it('maps invalid domain error message for non-LSPU addresses', () => {
    expect(validateUserEmail('user@gmail.com')).toBe(
      'Please use your official @lspu.edu.ph email address.',
    );
  });

  it('returns null for valid @lspu.edu.ph addresses', () => {
    expect(validateUserEmail('faculty@lspu.edu.ph')).toBeNull();
  });
});

describe('normalizeUserEmail', () => {
  it('normalizes email through whitespace trimming and lowercasing', () => {
    expect(normalizeUserEmail('  User.Name@LSPU.EDU.PH  ')).toBe('user.name@lspu.edu.ph');
    expect(normalizeUserEmail(null)).toBe('');
  });
});
