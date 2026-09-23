import {
  classifyInstitutionalEmailIssue,
  normalizeInstitutionalEmail,
} from '@equiped/types';

const ERROR_MESSAGES = {
  required: 'Email is required.',
  maxLength: 'Email must be 40 characters or fewer.',
  invalidDomain: 'Please use your official @lspu.edu.ph email address.',
} as const;

export function normalizeUserEmail(email?: string | null): string {
  return normalizeInstitutionalEmail(email);
}

export function validateUserEmail(email?: string | null): string | null {
  const issue = classifyInstitutionalEmailIssue(email);

  switch (issue) {
    case 'required':
      return ERROR_MESSAGES.required;
    case 'tooLong':
      return ERROR_MESSAGES.maxLength;
    case 'invalidDomain':
      return ERROR_MESSAGES.invalidDomain;
    case null:
      return null;
  }
}
