const LSPU_EMAIL_MAX_LENGTH = 40;
const LSPU_EMAIL_PATTERN = /^[^\s@]+@lspu\.edu\.ph$/i;

export type InstitutionalEmailIssue = 'required' | 'tooLong' | 'invalidDomain';

/**
 * Pure institutional email normalization.
 * Trims leading/trailing whitespace and converts to lowercase.
 * Returns empty string for null, undefined, or empty values.
 */
export function normalizeInstitutionalEmail(email?: string | null): string {
  return (email ?? '').trim().toLowerCase();
}

/**
 * Pure institutional email issue classification.
 * Evaluates trimmed email in sequence:
 * 1. 'required' if null, undefined, or empty after trimming
 * 2. 'tooLong' if length exceeds 40 characters
 * 3. 'invalidDomain' if not matching official @lspu.edu.ph pattern
 * 4. null if email satisfies all institutional constraints
 */
export function classifyInstitutionalEmailIssue(
  email?: string | null,
): InstitutionalEmailIssue | null {
  const trimmed = (email ?? '').trim();

  if (!trimmed) {
    return 'required';
  }

  if (trimmed.length > LSPU_EMAIL_MAX_LENGTH) {
    return 'tooLong';
  }

  if (!LSPU_EMAIL_PATTERN.test(trimmed)) {
    return 'invalidDomain';
  }

  return null;
}
