import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import {
  ArrowRight,
  CheckCircle,
  EnvelopeSimple,
  Eye,
  EyeSlash,
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
  const [showPassword, setShowPassword] = useState(false);
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
    <div className="min-h-screen lg:h-screen lg:overflow-hidden flex flex-col lg:flex-row bg-white font-sans selection:bg-primary selection:text-white">
      {/* Left Pane: Brand Hero */}
      <BrandHero />

      {/* Right Pane: Architectural Ledger Access Registry */}
      <div className="w-full lg:w-7/12 bg-white flex flex-col min-h-0">
        {/* Top Margin (Structural) */}
        <div className="hidden lg:block h-10 border-b border-slate-200 w-full shrink-0 bg-slate-50/50" />

        <div className="flex-1 flex flex-col lg:flex-row w-full h-full">
          {/* Left Column (Gutter) */}
          <div className="hidden lg:block w-16 xl:w-24 border-r border-slate-200 shrink-0 bg-slate-50/30" />

          {/* Main Content Column */}
          <div className="flex-1 flex flex-col justify-center relative py-1 sm:py-2">
            {/* Center Grid Block */}
            <div className="w-full bg-white relative">
              {/* Header Cell */}
              <div className="px-6 sm:px-10 lg:px-14 py-4 border-t border-b border-slate-200 bg-slate-50/40">
                <h2 className="text-2xl font-bold tracking-tight text-slate-900 mb-0.5">
                  {done
                    ? 'Registration Submitted'
                    : token
                      ? 'Verify Your Email'
                      : 'Create Faculty Account'}
                </h2>
                <p className="text-xs sm:text-sm text-slate-500 font-medium">
                  {done
                    ? 'Your email is verified. An administrator must approve your account before you can sign in.'
                    : token
                      ? `Enter the six-digit verification code sent to ${form.email}.`
                      : 'Use your official LSPU credentials to create your account.'}
                </p>
              </div>

              {done ? (
                <div className="flex flex-col">
                  <div className="border-b border-slate-200 bg-emerald-50/90 px-6 sm:px-10 lg:px-14 py-5 flex items-center gap-3 text-emerald-800">
                    <CheckCircle className="size-5 shrink-0 text-emerald-600" aria-hidden="true" />
                    <span className="text-sm font-semibold">
                      Your account registration is pending administrator approval.
                    </span>
                  </div>
                  <div className="px-6 sm:px-10 lg:px-14 py-6 text-sm text-slate-600 border-b border-slate-200 bg-slate-50/20">
                    We will send an email confirmation to <strong className="text-slate-900 font-semibold">{form.email}</strong> once your institutional account is verified and activated.
                  </div>
                  <div className="flex border-b border-slate-200">
                    <Link
                      to="/login"
                      className="w-full h-12 bg-[#1b3b87] hover:bg-[#142f70] active:bg-[#0f2354] text-white font-bold text-xs tracking-[0.08em] uppercase transition-colors flex items-center justify-center gap-2 group"
                    >
                      Return to Sign In
                      <ArrowRight className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              ) : token ? (
                <form onSubmit={verify} className="flex flex-col">
                  {/* Code Row */}
                  <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/[0.02] transition-colors">
                    <div className="px-6 sm:px-10 lg:px-4 py-3 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-[#1b3b87]/[0.03]">
                      <label
                        htmlFor="reg-code"
                        className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer select-none whitespace-nowrap"
                      >
                        Verification Code
                      </label>
                    </div>
                    <div className="px-6 sm:px-10 lg:px-6 py-2.5 flex flex-col justify-center w-full">
                      <input
                        id="reg-code"
                        autoFocus
                        inputMode="numeric"
                        pattern="[0-9]{6}"
                        maxLength={6}
                        value={otp}
                        onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                        placeholder="000000"
                        className="h-11 w-full rounded-none border-0 bg-transparent px-2 text-center text-lg sm:text-xl font-bold tracking-[0.5em] text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]/80 placeholder:text-slate-300"
                        required
                      />
                    </div>
                  </div>

                  {/* Error Row */}
                  {error && (
                    <div
                      role="alert"
                      className="border-b border-slate-200 bg-rose-50/90 px-6 sm:px-10 lg:px-14 py-3.5 flex items-center gap-3 text-rose-700"
                    >
                      <ShieldWarning className="size-4 shrink-0 text-rose-600" aria-hidden="true" />
                      <span className="text-xs sm:text-sm font-medium leading-relaxed">{error}</span>
                    </div>
                  )}

                  {/* Action Row */}
                  <div className="flex border-b border-slate-200">
                    <button
                      type="submit"
                      disabled={busy || otp.length !== 6}
                      className="w-full h-12 rounded-none bg-[#1b3b87] hover:bg-[#142f70] active:bg-[#0f2354] text-white font-bold text-xs tracking-[0.1em] uppercase transition-colors flex items-center justify-center gap-2.5 group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                    >
                      {busy ? (
                        <span className="flex items-center gap-2">
                          <Spinner className="w-4 h-4 animate-spin opacity-80" aria-hidden="true" />
                          Verifying Code...
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          Verify Email
                          <ArrowRight className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
                        </span>
                      )}
                    </button>
                  </div>

                  <div className="px-4 py-3 text-center text-xs font-medium text-slate-500 bg-slate-50/20 flex items-center justify-center gap-4">
                    <button
                      type="button"
                      onClick={resend}
                      disabled={busy}
                      className="font-bold text-[#1b3b87] hover:underline cursor-pointer uppercase tracking-wider disabled:opacity-50"
                    >
                      Resend Code
                    </button>
                    <span className="text-slate-300">|</span>
                    <Link to="/login" className="font-semibold text-slate-600 hover:text-slate-900 hover:underline">
                      Back to Sign In
                    </Link>
                  </div>
                </form>
              ) : (
                <form onSubmit={start} className="flex flex-col">
                  {/* Full Name Row */}
                  <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/[0.02] transition-colors">
                    <div className="px-6 sm:px-10 lg:px-4 py-2.5 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-[#1b3b87]/[0.03]">
                      <label
                        htmlFor="reg-name"
                        className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer select-none whitespace-nowrap"
                      >
                        Full Name
                      </label>
                    </div>
                    <div className="px-6 sm:px-10 lg:px-6 py-1.5 flex flex-col justify-center w-full">
                      <input
                        id="reg-name"
                        type="text"
                        value={form.name}
                        onChange={(e) => update('name', e.target.value)}
                        placeholder="Juan Dela Cruz"
                        className="h-10 w-full rounded-none border-0 bg-transparent px-2 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]/80"
                        required
                      />
                    </div>
                  </div>

                  {/* Email Row */}
                  <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/[0.02] transition-colors">
                    <div className="px-6 sm:px-10 lg:px-4 py-2.5 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-[#1b3b87]/[0.03]">
                      <label
                        htmlFor="reg-email"
                        className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer select-none whitespace-nowrap"
                      >
                        LSPU Email
                      </label>
                    </div>
                    <div className="px-6 sm:px-10 lg:px-6 py-1.5 flex flex-col justify-center w-full">
                      <input
                        id="reg-email"
                        type="email"
                        maxLength={40}
                        value={form.email}
                        onChange={(e) => update('email', e.target.value)}
                        placeholder="name@lspu.edu.ph"
                        className="h-10 w-full rounded-none border-0 bg-transparent px-2 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]/80"
                        required
                      />
                    </div>
                  </div>

                  {/* Faculty ID Row */}
                  <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/[0.02] transition-colors">
                    <div className="px-6 sm:px-10 lg:px-4 py-2.5 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-[#1b3b87]/[0.03]">
                      <label
                        htmlFor="reg-faculty-id"
                        className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer select-none whitespace-nowrap"
                      >
                        Faculty ID
                      </label>
                    </div>
                    <div className="px-6 sm:px-10 lg:px-6 py-1.5 flex flex-col justify-center w-full">
                      <input
                        id="reg-faculty-id"
                        type="text"
                        value={form.faculty_id}
                        onChange={(e) => update('faculty_id', e.target.value)}
                        placeholder="e.g. 2024-0012"
                        className="h-10 w-full rounded-none border-0 bg-transparent px-2 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]/80"
                        required
                      />
                    </div>
                  </div>

                  {/* Department Row */}
                  <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/[0.02] transition-colors">
                    <div className="px-6 sm:px-10 lg:px-4 py-2.5 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-[#1b3b87]/[0.03]">
                      <label
                        htmlFor="reg-dept"
                        className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer select-none whitespace-nowrap"
                      >
                        Department
                      </label>
                    </div>
                    <div className="px-6 sm:px-10 lg:px-6 py-1.5 flex flex-col justify-center w-full">
                      <input
                        id="reg-dept"
                        type="text"
                        value={form.department}
                        onChange={(e) => update('department', e.target.value)}
                        placeholder="College of Computer Studies"
                        className="h-10 w-full rounded-none border-0 bg-transparent px-2 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]/80"
                        required
                      />
                    </div>
                  </div>

                  {/* Program Row */}
                  <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/[0.02] transition-colors">
                    <div className="px-6 sm:px-10 lg:px-4 py-2.5 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-[#1b3b87]/[0.03]">
                      <label
                        htmlFor="reg-program"
                        className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer select-none whitespace-nowrap"
                      >
                        Program
                      </label>
                    </div>
                    <div className="px-6 sm:px-10 lg:px-6 py-1.5 flex flex-col justify-center w-full">
                      <input
                        id="reg-program"
                        type="text"
                        value={form.program}
                        onChange={(e) => update('program', e.target.value)}
                        placeholder="BSCS or BSInfoTech"
                        className="h-10 w-full rounded-none border-0 bg-transparent px-2 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]/80"
                        required
                      />
                    </div>
                  </div>

                  {/* Password Row */}
                  <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/[0.02] transition-colors">
                    <div className="px-6 sm:px-10 lg:px-4 py-2.5 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-[#1b3b87]/[0.03]">
                      <label
                        htmlFor="reg-password"
                        className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer select-none whitespace-nowrap"
                      >
                        Password
                      </label>
                    </div>
                    <div className="px-6 sm:px-10 lg:px-6 py-1.5 flex flex-col justify-center w-full">
                      <div className="relative flex items-center">
                        <input
                          id="reg-password"
                          type={showPassword ? 'text' : 'password'}
                          minLength={8}
                          value={form.password}
                          onChange={(e) => update('password', e.target.value)}
                          placeholder="At least 8 characters"
                          className="h-10 w-full rounded-none border-0 bg-transparent pl-2 pr-10 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]/80"
                          required
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-2 text-slate-400 hover:text-slate-600 focus:outline-none focus:text-[#1b3b87] cursor-pointer flex items-center justify-center p-1 rounded-xs transition-colors"
                          aria-label={showPassword ? 'Hide password' : 'Show password'}
                        >
                          {showPassword ? (
                            <EyeSlash className="size-4" aria-hidden="true" />
                          ) : (
                            <Eye className="size-4" aria-hidden="true" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Error Row */}
                  {error && (
                    <div
                      role="alert"
                      className="border-b border-slate-200 bg-rose-50/90 px-6 sm:px-8 py-3 flex items-center gap-3 text-rose-700"
                    >
                      <ShieldWarning className="size-4 shrink-0 text-rose-600" aria-hidden="true" />
                      <span className="text-xs font-medium leading-relaxed">{error}</span>
                    </div>
                  )}

                  {/* Action Row */}
                  <div className="flex border-b border-slate-200">
                    <button
                      type="submit"
                      disabled={busy}
                      className="w-full h-12 rounded-none bg-[#1b3b87] hover:bg-[#142f70] active:bg-[#0f2354] text-white font-bold text-xs tracking-[0.1em] uppercase transition-colors flex items-center justify-center gap-2.5 group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                    >
                      {busy ? (
                        <span className="flex items-center gap-2">
                          <Spinner className="w-4 h-4 animate-spin opacity-80" aria-hidden="true" />
                          Submitting Registration...
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          Send Verification Code
                          <EnvelopeSimple className="w-4 h-4 opacity-70 group-hover:opacity-100 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
                        </span>
                      )}
                    </button>
                  </div>
                  <div className="px-6 py-3 text-center text-xs font-medium text-slate-500 bg-slate-50/20">
                    Already registered?{' '}
                    <Link to="/login" className="font-bold text-[#1b3b87] hover:underline">
                      Sign In
                    </Link>
                  </div>
                  <div className="py-3 text-center text-[11px] text-slate-400 lg:hidden">
                    © {new Date().getFullYear()} Laguna State Polytechnic University · Santa Cruz Campus
                  </div>
                </form>
              )}
            </div>
          </div>

          {/* Right Column (Gutter) */}
          <div className="hidden lg:block w-16 xl:w-24 border-l border-slate-200 shrink-0 bg-slate-50/30" />
        </div>

        {/* Bottom Margin (Structural Two-Sided Ledger Bar) */}
        <div className="hidden lg:flex h-10 border-t border-slate-200 w-full shrink-0 bg-slate-50/50 items-center justify-between px-8 text-[11px] text-slate-500 font-medium">
          <span>College of Computer Studies</span>
          <span>© {new Date().getFullYear()} Laguna State Polytechnic University · Santa Cruz Campus</span>
        </div>
      </div>
    </div>
  );
}
