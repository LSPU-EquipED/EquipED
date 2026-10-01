import { Link } from '@tanstack/react-router';
import {
  ArrowRight,
  CheckCircle,
  ShieldWarning,
  Spinner,
} from '@phosphor-icons/react';
import { AuthPageLayout } from '../components/AuthPageLayout';
import { AuthField } from '../components/AuthField';
import { AuthFormHeader } from '../components/AuthFormHeader';
import { RegistrationIntakeForm } from '../components/RegistrationIntakeForm';
import { useRegistrationForm } from '../hooks/useRegistrationForm';

export function RegistrationPage() {
  const {
    form,
    token,
    otp,
    setOtp,
    done,
    pendingAction,
    pendingLabel,
    busy,
    error,
    programError,
    programRef,
    showPassword,
    setShowPassword,
    update,
    selectProgram,
    start,
    verify,
    resend,
  } = useRegistrationForm();

  return (
    <AuthPageLayout wide={!token && !done}>
      <AuthFormHeader
        title={
          done
            ? 'Registration submitted'
            : token
              ? 'Verify your email'
              : 'Create faculty account'
        }
        description={
          done
            ? 'Your email is verified.'
            : token
              ? `Enter the six-digit code sent to ${form.email}.`
              : 'Use your LSPU email and choose an EquipED password.'
        }
      />
      {done ? (
        <div className="auth-form-fields">
          <div className="auth-form-note flex items-start gap-3">
            <CheckCircle
              className="mt-0.5 size-5 shrink-0 text-success"
              aria-hidden="true"
            />
            <p>
              An administrator must approve your account before you can sign in.
            </p>
          </div>
          <Link to="/login" className="auth-form-submit">
            Return to sign in{' '}
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      ) : token ? (
        <form onSubmit={verify} className="auth-form-fields">
          <AuthField id="reg-code" label="Verification code">
            <input
              id="reg-code"
              autoComplete="one-time-code"
              aria-describedby={error ? 'registration-error' : undefined}
              autoFocus
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={otp}
              onChange={(event) =>
                setOtp(event.target.value.replace(/\D/g, ''))
              }
              placeholder="000000"
              className="auth-form-control text-center tabular-nums tracking-[0.25em]"
              required
            />
          </AuthField>
          {error && (
            <div
              id="registration-error"
              role="alert"
              className="auth-form-alert"
            >
              <ShieldWarning
                className="mt-0.5 size-4 shrink-0"
                aria-hidden="true"
              />
              <span>{error}</span>
            </div>
          )}
          <button
            type="submit"
            aria-busy={pendingAction === 'verify'}
            disabled={busy || otp.length !== 6}
            className="auth-form-submit"
          >
            {pendingAction === 'verify' ? (
              <Spinner
                className="size-4 animate-spin motion-reduce:animate-none"
                aria-hidden="true"
              />
            ) : (
              <ArrowRight className="size-4" aria-hidden="true" />
            )}
            {pendingAction === 'verify' ? pendingLabel : 'Verify email'}
          </button>
          <div className="auth-form-options">
            <button
              type="button"
              onClick={resend}
              disabled={busy}
              aria-busy={pendingAction === 'resend'}
              className="auth-form-link flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {pendingAction === 'resend' && (
                <Spinner
                  className="size-4 animate-spin motion-reduce:animate-none"
                  aria-hidden="true"
                />
              )}
              {pendingAction === 'resend' ? pendingLabel : 'Resend code'}
            </button>
            <Link to="/login" className="auth-form-link">
              Back to sign in
            </Link>
          </div>
        </form>
      ) : (
        <RegistrationIntakeForm
          form={form}
          update={update}
          selectProgram={selectProgram}
          start={start}
          showPassword={showPassword}
          setShowPassword={setShowPassword}
          programRef={programRef}
          programError={programError}
          error={error}
          busy={busy}
          pendingLabel={pendingLabel}
        />
      )}
      <span role="status" aria-live="polite" className="sr-only">
        {pendingLabel}
      </span>
    </AuthPageLayout>
  );
}
