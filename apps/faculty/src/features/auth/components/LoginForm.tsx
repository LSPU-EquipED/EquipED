import { useEffect, useState, useRef } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ResetPasswordModal, useAuth, navigateCrossApp } from '@equiped/auth';
import { useLoginForm } from '../hooks/useLoginForm';
import { ShieldWarning, ArrowRight, Spinner } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import { AuthPageLayout } from './AuthPageLayout';
import { AuthField } from './AuthField';
import { AuthPasswordInput } from './AuthPasswordInput';
import { AuthFormHeader } from './AuthFormHeader';

export function LoginForm() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const {
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
  } = useLoginForm();

  const isRedirecting = auth.status === 'authenticated';
  const isBusy = isSubmitting || isRedirecting;
  const pendingLabel = isRedirecting
    ? 'Opening your workspace…'
    : 'Signing in…';

  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const wasResetOpen = useRef(showResetDialog);

  useEffect(() => {
    document.title = 'Sign in — EquipED';
  }, []);

  useEffect(() => {
    if (auth.status === 'authenticated') {
      if (auth.user?.role === 'admin') {
        navigateCrossApp('/admin');
      } else {
        void navigate({ to: '/dashboard' });
      }
    }
  }, [auth.status, auth.user, navigate]);

  useEffect(() => {
    if (wasResetOpen.current && !showResetDialog) {
      triggerRef.current?.focus();
    }
    wasResetOpen.current = showResetDialog;
  }, [showResetDialog]);

  return (
    <>
      <AuthPageLayout>
        <AuthFormHeader
          title="Sign in"
          description="Use your LSPU email and EquipED password."
        />
        <form onSubmit={handleSubmit} className="auth-form-fields">
          <AuthField id="login-email" label="Email">
            <input
              id="login-email"
              type="email"
              maxLength={40}
              inputMode="email"
              autoComplete="email"
              autoFocus
              placeholder="name@lspu.edu.ph"
              className="auth-form-control"
              value={email}
              onChange={(event) => {
                auth.clearError();
                setEmail(event.target.value);
                setEmailHint('');
              }}
              onBlur={handleEmailBlur}
              required
              aria-invalid={Boolean(emailHint)}
              aria-describedby={
                emailHint
                  ? 'login-email-hint'
                  : auth.error
                    ? 'login-error'
                    : undefined
              }
            />
            {emailHint && (
              <p id="login-email-hint" role="alert" className="auth-form-hint">
                {emailHint}
              </p>
            )}
          </AuthField>
          <AuthField id="login-password" label="Password">
            <AuthPasswordInput
              id="login-password"
              visible={showPassword}
              onVisibilityChange={setShowPassword}
              autoComplete="current-password"
              value={password}
              placeholder="Enter your password"

              onChange={(event) => {
                auth.clearError();
                setPassword(event.target.value);
                setPasswordHint('');
              }}
              onBlur={handlePasswordBlur}
              required
              aria-invalid={Boolean(passwordHint)}
              aria-describedby={
                passwordHint
                  ? 'login-password-hint'
                  : auth.error
                    ? 'login-error'
                    : undefined
              }
            />
            {passwordHint && (
              <p
                id="login-password-hint"
                role="alert"
                className="auth-form-hint"
              >
                {passwordHint}
              </p>
            )}
          </AuthField>
          <div className="auth-form-options">
            <label
              htmlFor="login-remember"
              className="flex cursor-pointer items-center gap-2"
            >
              <input
                id="login-remember"
                type="checkbox"
                className="size-4 shrink-0 cursor-pointer accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                checked={rememberEmail}
                onChange={(event) => setRememberEmail(event.target.checked)}
              />
              Remember my email
            </label>
            <button
              ref={triggerRef}
              type="button"
              onClick={() => setShowResetDialog(true)}
              className="auth-form-link"
            >
              Reset password
            </button>
          </div>
          {auth.error && (
            <div id="login-error" role="alert" className="auth-form-alert">
              <ShieldWarning
                className="mt-0.5 size-4 shrink-0"
                aria-hidden="true"
              />
              <span>{auth.error}</span>
            </div>
          )}
          <button
            type="submit"
            disabled={isBusy}
            aria-busy={isBusy}
            className="auth-form-submit"
          >
            {isBusy ? (
              <>
                <Spinner
                  className="size-4 shrink-0 animate-spin motion-reduce:animate-none"
                  aria-hidden="true"
                />
                {pendingLabel}
              </>
            ) : (
              <>
                Sign in <ArrowRight className="size-4" aria-hidden="true" />
              </>
            )}
          </button>
          <span role="status" aria-live="polite" className="sr-only">
            {isBusy ? pendingLabel : ''}
          </span>
          <div className="auth-form-secondary">
            <span>New to EquipED?</span>
            <Link to="/register" className="auth-form-link">
              Create an account
            </Link>
          </div>
        </form>
      </AuthPageLayout>
      <ResetPasswordModal
        isOpen={showResetDialog}
        onClose={() => setShowResetDialog(false)}
      />
    </>
  );
}
