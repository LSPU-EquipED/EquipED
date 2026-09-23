import { useState, type FormEvent } from 'react';
import { useAuth } from '@equiped/auth';
import {
  classifyInstitutionalEmailIssue,
  normalizeInstitutionalEmail,
} from '@equiped/types';

export function useLoginForm() {
  const auth = useAuth();
  const [email, setEmail] = useState(() => localStorage.getItem('remembered_email') || '');
  const [password, setPassword] = useState('');
  const [rememberEmail, setRememberEmail] = useState(
    () => !!localStorage.getItem('remembered_email'),
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [emailHint, setEmailHint] = useState('');
  const [passwordHint, setPasswordHint] = useState('');

  const handleEmailBlur = () => {
    const issue = classifyInstitutionalEmailIssue(email);
    if (issue === 'tooLong') {
      setEmailHint('Email must be 40 characters or fewer.');
    } else if (issue === 'invalidDomain') {
      setEmailHint('Please use your official @lspu.edu.ph email address.');
    } else {
      setEmailHint('');
    }
  };

  const handlePasswordBlur = () => {
    if (password && password.length < 8) {
      setPasswordHint('Minimum 8 characters required.');
    } else {
      setPasswordHint('');
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedEmail = normalizeInstitutionalEmail(email);
    const issue = classifyInstitutionalEmailIssue(normalizedEmail);
    if (issue !== null) {
      setEmailHint(
        issue === 'tooLong'
          ? 'Email must be 40 characters or fewer.'
          : 'Please use your official @lspu.edu.ph email address.',
      );
      return;
    }
    auth.clearError();
    setIsSubmitting(true);

    try {
      await auth.login({ email: normalizedEmail, password });
      if (rememberEmail) {
        localStorage.setItem('remembered_email', normalizedEmail);
      } else {
        localStorage.removeItem('remembered_email');
      }
    } catch {
      // Error state is normalized in the auth provider.
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    email,
    setEmail,
    password,
    setPassword,
    rememberEmail,
    setRememberEmail,
    isSubmitting,
    emailHint,
    setEmailHint,
    passwordHint,
    setPasswordHint,
    handleEmailBlur,
    handlePasswordBlur,
    handleSubmit,
    authError: auth.error,
    clearAuthError: auth.clearError,
  };
}
