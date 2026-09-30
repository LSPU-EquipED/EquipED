import { useEffect, useState, useRef } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { BrandHero, ResetPasswordModal, useAuth, navigateCrossApp } from '@equiped/auth';
import { useLoginForm } from '../hooks/useLoginForm';
import { ShieldWarning, ArrowRight, Spinner, Eye, EyeSlash } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';

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
  const pendingLabel = isRedirecting ? 'Opening your workspace…' : 'Signing in…';

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
    <div className="min-h-screen flex flex-col lg:flex-row bg-white font-sans selection:bg-primary selection:text-white">
      {/* Left Pane: Brand Hero */}
      <BrandHero />

      {/* Right Pane: The Architectural Ledger */}
      <main className="w-full lg:w-7/12 bg-white flex flex-col min-h-0">
        {/* Top Margin (Structural) */}
        <div className="hidden lg:block h-16 border-b border-slate-200 w-full shrink-0 bg-slate-50/50" />

        <div className="flex-1 flex flex-col lg:flex-row w-full h-full">
          {/* Left Column (Gutter) */}
          <div className="hidden lg:block w-16 xl:w-24 border-r border-slate-200 shrink-0 bg-slate-50/30" />

          {/* Main Content Column */}
          <div className="flex-1 flex flex-col justify-center relative py-8 lg:py-0">
            {/* Center Grid Block */}
            <div className="w-full bg-white relative">
              {/* Header Cell */}
              <div className="px-6 sm:px-10 lg:px-14 py-8 lg:py-10 border-t border-b border-slate-200 bg-slate-50/40">
                <h1 className="text-2xl lg:text-3xl font-bold tracking-tight text-slate-900 mb-1">
                  Sign in
                </h1>
                <p className="text-xs sm:text-sm text-slate-500 font-medium">
                  Use your LSPU email and password to sign in.
                </p>
              </div>
              {/* Ledger Form */}
              <form onSubmit={handleSubmit} className="flex flex-col">
                {/* Email Row */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-primary/[0.02] transition-colors">
                  <div className="px-6 sm:px-10 lg:px-4 py-4 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-primary/[0.03]">
                    <label
                      htmlFor="login-email"
                      className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-primary cursor-pointer select-none whitespace-nowrap"
                    >
                      Email
                    </label>
                  </div>
                  <div className="px-6 sm:px-10 lg:px-6 py-2.5 lg:py-3 flex flex-col justify-center w-full">
                    <input
                      id="login-email"
                      type="email"
                      maxLength={40}
                      inputMode="email"
                      autoComplete="email"
                      autoFocus
                      placeholder="name@lspu.edu.ph"
                      className="h-12 w-full rounded-none border-0 bg-transparent px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/80 placeholder:text-slate-400 font-medium text-slate-900"
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
                        emailHint ? 'login-email-hint' : auth.error ? 'login-error' : undefined
                      }
                    />
                    {emailHint && (
                      <p
                        id="login-email-hint"
                        className="text-[11px] font-semibold text-rose-600 px-2 pt-1 transition-all"
                      >
                        {emailHint}
                      </p>
                    )}
                  </div>
                </div>

                {/* Password Row */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-primary/[0.02] transition-colors">
                  <div className="px-6 sm:px-10 lg:px-4 py-4 lg:py-0 lg:border-r border-slate-200 flex items-center lg:items-center justify-start lg:justify-center text-left lg:text-center transition-colors group-focus-within:bg-primary/[0.03]">
                    <label
                      htmlFor="login-password"
                      className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-primary cursor-pointer select-none whitespace-nowrap"
                    >
                      Password
                    </label>
                  </div>
                  <div className="px-6 sm:px-10 lg:px-6 py-2.5 lg:py-3 flex flex-col justify-center w-full">
                    <div className="relative flex items-center">
                      <input
                        id="login-password"
                        type={showPassword ? 'text' : 'password'}
                        autoComplete="current-password"
                        value={password}
                        placeholder="Enter your password"
                        className="h-12 w-full rounded-none border-0 bg-transparent pl-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-ring/80 placeholder:text-slate-400 font-medium text-slate-900"
                        onChange={(event) => {
                          auth.clearError();
                          setPassword(event.target.value);
                          setPasswordHint('');
                        }}
                        onBlur={handlePasswordBlur}
                        required
                        aria-invalid={Boolean(passwordHint)}
                        aria-describedby={passwordHint ? 'login-password-hint' : auth.error ? 'login-error' : undefined}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-0 size-10 text-slate-400 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 cursor-pointer flex items-center justify-center p-1.5 rounded-xs transition-colors"
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                        title={showPassword ? 'Hide password' : 'Show password'}
                        aria-pressed={showPassword}
                      >
                        {showPassword ? (
                          <EyeSlash className="size-5" aria-hidden="true" />
                        ) : (
                          <Eye className="size-5" aria-hidden="true" />
                        )}
                      </button>
                    </div>
                    {passwordHint && (
                      <p id="login-password-hint" className="text-sm text-warning px-2 pt-1">
                        {passwordHint}
                      </p>
                    )}
                  </div>
                </div>

                {/* Remember & Reset Row */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-slate-50/50 transition-colors">
                  <div className="hidden lg:block lg:border-r border-slate-200 bg-slate-50/30" />
                  <div className="px-6 sm:px-10 lg:px-6 py-3.5 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2.5">
                      <input
                        id="login-remember"
                        type="checkbox"
                        className="size-4 rounded-none border-slate-300 text-primary focus:ring-2 focus:ring-ring cursor-pointer accent-primary shrink-0"
                        checked={rememberEmail}
                        onChange={(event) => setRememberEmail(event.target.checked)}
                      />
                      <label
                        htmlFor="login-remember"
                        className="text-xs font-medium text-slate-600 hover:text-slate-900 select-none cursor-pointer transition-colors"
                      >
                        Remember my email
                      </label>
                    </div>
                    <button
                      ref={triggerRef}
                      type="button"
                      onClick={() => setShowResetDialog(true)}
                      className="text-[11px] font-bold text-primary hover:underline cursor-pointer opacity-80 hover:opacity-100 uppercase tracking-wider focus:outline-none focus:ring-2 focus:ring-ring transition-opacity shrink-0"
                    >
                      Reset password
                    </button>
                  </div>
                </div>

                {/* Error Row (Conditionally Rendered) */}
                {auth.error && (
                  <div
                    id="login-error"
                    role="alert"
                    className="border-b border-slate-200 bg-rose-50/90 px-6 sm:px-10 lg:px-14 py-3.5 flex items-center gap-3 text-rose-700"
                  >
                    <ShieldWarning
                      className="size-4 shrink-0 text-rose-600"
                      aria-hidden="true"
                    />
                    <span className="text-xs sm:text-sm font-medium leading-relaxed">
                      {auth.error}
                    </span>
                  </div>
                )}

                {/* Action Row */}
                <div className="flex border-b border-slate-200">
                  <button
                    type="submit"
                    disabled={isBusy}
                    aria-busy={isBusy}
                    className="w-full h-14 rounded-none bg-primary hover:bg-primary-strong active:bg-primary-strong text-white font-bold text-xs tracking-[0.1em] uppercase transition-colors flex items-center justify-center gap-3 group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {isBusy ? (
                      <span className="flex items-center gap-3">
                        <Spinner className="size-4 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                        {pendingLabel}
                      </span>
                    ) : (
                      <span className="flex items-center gap-3">
                        Sign in
                        <ArrowRight className="w-4 h-4 opacity-70 group-hover:opacity-100 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
                      </span>
                    )}
                  </button>
                </div>
                <span role="status" aria-live="polite" className="sr-only">
                  {isBusy ? pendingLabel : ''}
                </span>
                <div className="px-6 py-4 text-center text-xs font-medium text-slate-500 bg-slate-50/20">
                  New to EquipED?{' '}
                  <Link to="/register" className="font-bold text-primary hover:underline">
                    Create an account
                  </Link>
                </div>
                <div className="py-4 text-center text-[11px] text-slate-400 lg:hidden">
                  © {new Date().getFullYear()} Laguna State Polytechnic University · Santa Cruz Campus
                </div>
              </form>
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
      </main>

      {/* Password Reset Modal */}
      <ResetPasswordModal isOpen={showResetDialog} onClose={() => setShowResetDialog(false)} />
    </div>
  );
}
