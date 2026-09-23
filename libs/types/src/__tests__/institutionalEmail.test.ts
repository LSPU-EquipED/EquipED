import { describe, expect, it } from 'vitest';
import {
  classifyInstitutionalEmailIssue,
  normalizeInstitutionalEmail,
} from '../institutionalEmail';

describe('classifyInstitutionalEmailIssue', () => {
  it('classifies missing or whitespace inputs as required', () => {
    expect(classifyInstitutionalEmailIssue(undefined)).toBe('required');
    expect(classifyInstitutionalEmailIssue(null)).toBe('required');
    expect(classifyInstitutionalEmailIssue('')).toBe('required');
    expect(classifyInstitutionalEmailIssue('   ')).toBe('required');
  });

  it('classifies inputs exceeding 40 characters as tooLong, taking precedence over invalidDomain', () => {
    // 41 characters ending with @lspu.edu.ph
    const validDomain41 = `${'a'.repeat(41 - '@lspu.edu.ph'.length)}@lspu.edu.ph`;
    expect(validDomain41.length).toBe(41);
    expect(classifyInstitutionalEmailIssue(validDomain41)).toBe('tooLong');

    // 41 characters with invalid domain
    const invalidDomain41 = 'a'.repeat(41);
    expect(classifyInstitutionalEmailIssue(invalidDomain41)).toBe('tooLong');

    // Padded whitespace around 41 characters
    expect(classifyInstitutionalEmailIssue(`  ${validDomain41}  `)).toBe('tooLong');
  });

  it('classifies non-@lspu.edu.ph addresses <= 40 chars as invalidDomain', () => {
    expect(classifyInstitutionalEmailIssue('faculty@gmail.com')).toBe('invalidDomain');
    expect(classifyInstitutionalEmailIssue('faculty@lspu.edu')).toBe('invalidDomain');
    expect(classifyInstitutionalEmailIssue('lspu.edu.ph')).toBe('invalidDomain');
    expect(classifyInstitutionalEmailIssue('@lspu.edu.ph')).toBe('invalidDomain');
    expect(classifyInstitutionalEmailIssue('user name@lspu.edu.ph')).toBe('invalidDomain');
  });

  it('returns null for valid @lspu.edu.ph addresses within 40 characters', () => {
    expect(classifyInstitutionalEmailIssue('valid.user@lspu.edu.ph')).toBeNull();
    expect(classifyInstitutionalEmailIssue('VALID.USER@LSPU.EDU.PH')).toBeNull();
    expect(classifyInstitutionalEmailIssue('  valid.user@lspu.edu.ph  ')).toBeNull();

    // Exactly 40 characters: 28 prefix chars + 12 domain chars
    const exact40 = `${'a'.repeat(28)}@lspu.edu.ph`;
    expect(exact40.length).toBe(40);
    expect(classifyInstitutionalEmailIssue(exact40)).toBeNull();
  });
});

describe('normalizeInstitutionalEmail', () => {
  it('trims leading/trailing whitespace and converts to lowercase', () => {
    expect(normalizeInstitutionalEmail('  Faculty.User@LSPU.EDU.PH  ')).toBe(
      'faculty.user@lspu.edu.ph',
    );
  });

  it('handles null and undefined gracefully by returning empty string', () => {
    expect(normalizeInstitutionalEmail(null)).toBe('');
    expect(normalizeInstitutionalEmail(undefined)).toBe('');
    expect(normalizeInstitutionalEmail('')).toBe('');
  });
});
