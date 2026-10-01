import type { FormEvent, RefObject } from 'react';
import { Link } from '@tanstack/react-router';
import { EnvelopeSimple, ShieldWarning, Spinner } from '@phosphor-icons/react';
import { Dropdown } from '@equiped/ui';
import { CANONICAL_PROGRAMS } from '@equiped/types';
import type { RegistrationBody } from '../api/registration.api';
import { AuthField } from './AuthField';
import { AuthPasswordInput } from './AuthPasswordInput';

const programOptions = CANONICAL_PROGRAMS.map((program) => ({
  value: program,
  label: program,
}));

type RegistrationIntakeFormProps = {
  form: RegistrationBody;
  update: (key: keyof RegistrationBody, value: string) => void;
  selectProgram: (value: string) => void;
  start: (event: FormEvent) => Promise<void>;
  showPassword: boolean;
  setShowPassword: (visible: boolean) => void;
  programRef: RefObject<HTMLButtonElement>;
  programError: string;
  error: string;
  busy: boolean;
  pendingLabel: string;
};

export function RegistrationIntakeForm({
  form,
  update,
  selectProgram,
  start,
  showPassword,
  setShowPassword,
  programRef,
  programError,
  error,
  busy,
  pendingLabel,
}: RegistrationIntakeFormProps) {
  return (
    <form onSubmit={start} className="auth-form-fields">
      <fieldset className="auth-form-group">
        <legend className="sr-only">Account details</legend>
        <AuthField id="reg-name" label="Full name">
          <input
            id="reg-name"
            autoComplete="name"
            type="text"
            value={form.name}
            onChange={(event) => update('name', event.target.value)}
            placeholder="Juan Dela Cruz"
            className="auth-form-control"
            required
          />
        </AuthField>
        <AuthField id="reg-email" label="LSPU email">
          <input
            id="reg-email"
            autoComplete="email"
            type="email"
            maxLength={40}
            value={form.email}
            onChange={(event) => update('email', event.target.value)}
            placeholder="name@lspu.edu.ph"
            className="auth-form-control"
            required
          />
        </AuthField>
        <AuthField id="reg-password" label="Password">
          <AuthPasswordInput
            id="reg-password"
            autoComplete="new-password"
            visible={showPassword}
            onVisibilityChange={setShowPassword}
            minLength={8}
            value={form.password}
            onChange={(event) => update('password', event.target.value)}
            placeholder="At least 8 characters"

            required
          />
        </AuthField>
      </fieldset>
      <fieldset className="auth-form-group">
        <legend className="auth-form-group-title">Faculty details</legend>
        <AuthField id="reg-dept" label="Department">
          <input
            id="reg-dept"
            type="text"
            value={form.department}
            onChange={(event) => update('department', event.target.value)}
            placeholder="College of Computer Studies"
            className="auth-form-control"
            required
          />
        </AuthField>
        <div className="auth-form-pair">
          <AuthField id="reg-faculty-id" label="Faculty ID">
            <input
              id="reg-faculty-id"
              type="text"
              value={form.faculty_id}
              onChange={(event) => update('faculty_id', event.target.value)}
              placeholder="e.g. 2024-0012"
              className="auth-form-control"
              required
            />
          </AuthField>
          <AuthField id="reg-program" label="Program">
            <Dropdown
              ref={programRef}
              id="reg-program"
              aria-label="Program"
              name="program"
              value={form.program}
              onChange={selectProgram}
              options={programOptions}
              placeholder="Select program"
              size="md"
              variant="default"
              required
              error={programError || undefined}
              containerClassName="w-full"
              className="auth-form-control"
              menuClassName="w-full min-w-0"
            />
          </AuthField>
        </div>
      </fieldset>
      {error && (
        <div id="registration-error" role="alert" className="auth-form-alert">
          <ShieldWarning
            className="mt-0.5 size-4 shrink-0"
            aria-hidden="true"
          />
          <span>{error}</span>
        </div>
      )}
      <button
        type="submit"
        aria-busy={busy}
        disabled={busy}
        className="auth-form-submit"
      >
        {busy ? (
          <Spinner
            className="size-4 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
        ) : (
          <EnvelopeSimple className="size-4" aria-hidden="true" />
        )}
        {busy ? pendingLabel : 'Send verification code'}
      </button>
      <div className="auth-form-secondary">
        <span>Already registered?</span>
        <Link to="/login" className="auth-form-link">
          Sign in
        </Link>
      </div>
    </form>
  );
}
