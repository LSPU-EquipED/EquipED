import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import {
  ArrowRight,
  CheckCircle,
  EnvelopeSimple,
  ShieldWarning,
  Spinner,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { registrationApi, type RegistrationBody } from '../api/registration.api';
import { BrandHero } from '../components/BrandHero';

const initialForm: RegistrationBody = {
  name: '',
  email: '',
  password: '',
  faculty_id: '',
  department: '',
  program: '',
};

export function RegistrationPage() {
  const [form, setForm] = useState(initialForm);
  const [token, setToken] = useState<string | null>(null);
  const [otp, setOtp] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const update = (key: keyof RegistrationBody, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const start = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const response = await registrationApi.start({
        ...form,
        email: form.email.trim().toLowerCase(),
      });
      setToken(response.registration_token);
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to start registration.'));
    } finally {
      setBusy(false);
    }
  };
  const verify = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token) return;
    setError('');
    setBusy(true);
    try {
      await registrationApi.verify(token, otp);
      setDone(true);
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to verify the code.'));
    } finally {
      setBusy(false);
    }
  };
  const resend = async () => {
    if (!token) return;
    setError('');
    setBusy(true);
    try {
      await registrationApi.resend(token);
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to resend the code.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-white font-sans">
      <BrandHero />
      <main className="w-full lg:w-7/12 flex items-center justify-center py-10 px-6 sm:px-12">
        <section className="w-full max-w-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 bg-slate-50/50 px-7 py-7">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#1b3b87]">
              EquipED access registry
            </p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
              {done
                ? 'Registration submitted'
                : token
                  ? 'Verify your email'
                  : 'Create faculty account'}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {done
                ? 'Your email is verified. An administrator must approve your account before you can sign in.'
                : token
                  ? `Enter the six-digit code sent to ${form.email}.`
                  : 'Use your official LSPU email. All registrations are reviewed by an administrator.'}
            </p>
          </div>
          {done ? (
            <div className="p-7 space-y-5">
              <div className="flex gap-3 border border-[#3b963e]/30 bg-[#3b963e]/10 p-4 text-sm font-semibold text-[#256b2a]">
                <CheckCircle className="size-5 shrink-0" /> Your account is pending admin approval.
              </div>
              <p className="text-sm text-slate-600">
                We will email you when your account is approved.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 text-sm font-bold text-[#1b3b87] hover:underline"
              >
                Return to sign in <ArrowRight className="size-4" />
              </Link>
            </div>
          ) : token ? (
            <form onSubmit={verify} className="p-7 space-y-5">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">
                Verification code
                <input
                  autoFocus
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  className="mt-2 h-14 w-full border border-slate-200 px-4 text-center text-2xl font-bold tracking-[0.5em] text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                  required
                />
              </label>
              {error && <Error text={error} />}
              <button
                disabled={busy || otp.length !== 6}
                className="h-12 w-full bg-[#1b3b87] text-sm font-bold uppercase tracking-wider text-white disabled:opacity-50"
              >
                {busy ? <Spinner className="mx-auto size-5 animate-spin" /> : 'Verify email'}
              </button>
              <button
                type="button"
                onClick={resend}
                disabled={busy}
                className="w-full text-xs font-bold uppercase tracking-wider text-[#1b3b87] hover:underline"
              >
                Resend code
              </button>
            </form>
          ) : (
            <form onSubmit={start} className="p-7 space-y-4">
              {(
                [
                  ['name', 'Full name', 'Juan Dela Cruz'],
                  ['email', 'LSPU email', 'name@lspu.edu.ph'],
                  ['faculty_id', 'Faculty / employee ID', 'Faculty ID'],
                  ['department', 'Department or office', 'College of Computer Studies'],
                  ['program', 'Program affiliation', 'BSCS or BSInfoTech'],
                ] as const
              ).map(([key, label, placeholder]) => (
                <label
                  key={key}
                  className="block text-xs font-bold uppercase tracking-wider text-slate-500"
                >
                  {label}
                  <input
                    type={key === 'email' ? 'email' : 'text'}
                    maxLength={key === 'email' ? 40 : undefined}
                    value={form[key]}
                    onChange={(e) => update(key, e.target.value)}
                    placeholder={placeholder}
                    className="mt-2 h-11 w-full border border-slate-200 px-3 text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                    required
                  />
                </label>
              ))}
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">
                Password
                <input
                  type="password"
                  minLength={8}
                  value={form.password}
                  onChange={(e) => update('password', e.target.value)}
                  placeholder="At least 8 characters"
                  className="mt-2 h-11 w-full border border-slate-200 px-3 text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                  required
                />
              </label>
              {error && <Error text={error} />}
              <button
                disabled={busy}
                className="mt-2 flex h-12 w-full items-center justify-center gap-2 bg-[#1b3b87] text-sm font-bold uppercase tracking-wider text-white disabled:opacity-50"
              >
                {busy ? (
                  <Spinner className="size-5 animate-spin" />
                ) : (
                  <>
                    Send verification code <EnvelopeSimple className="size-4" />
                  </>
                )}
              </button>
              <p className="text-center text-xs font-semibold text-slate-500">
                Already registered?{' '}
                <Link to="/login" className="text-[#1b3b87] hover:underline">
                  Sign in
                </Link>
              </p>
            </form>
          )}
        </section>
      </main>
    </div>
  );
}
function Error({ text }: { text: string }) {
  return (
    <div
      role="alert"
      className="flex gap-2 border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-3 text-sm font-semibold text-[#b91c1c]"
    >
      <ShieldWarning className="size-4 shrink-0" />
      {text}
    </div>
  );
}
