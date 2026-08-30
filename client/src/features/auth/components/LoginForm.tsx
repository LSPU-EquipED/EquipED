import { useEffect, useState, useRef } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useAuth } from '../hooks/useAuth';
import { useLoginForm } from '../hooks/useLoginForm';
import { ShieldWarning, ArrowRight, Spinner, Eye, EyeSlash } from '@phosphor-icons/react';
import { BrandHero } from './BrandHero';
import { ResetPasswordModal } from './ResetPasswordModal';

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

  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const wasResetOpen = useRef(showResetDialog);

  useEffect(() => {
    document.title = 'Sign In — EquipED';
  }, []);

  useEffect(() => {
    if (auth.status === 'authenticated') {
      const target = auth.user?.role === 'admin' ? '/admin' : '/dashboard';
      void navigate({ to: target });
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
      <div className="w-full lg:w-7/12 bg-white flex flex-col min-h-0">
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
              <div className="px-6 sm:px-10 lg:px-14 py-8 lg:py-10 border-t border-b border-slate-200 bg-slate-50/30 flex items-stretch gap-4">
                <div className="w-0.5 self-stretch bg-[#1b3b87] shrink-0" aria-hidden="true" />
                <div className="flex-1">
                  <h2 className="text-2xl lg:text-3xl font-bold tracking-tight text-slate-900 mb-2">
                    Sign In
                  </h2>
                  <p className="text-sm text-slate-600 font-medium">
                    Enter your LSPU email and password to continue.
                  </p>
                </div>
              </div>

              {/* Ledger Form */}
              <form onSubmit={handleSubmit} className="flex flex-col">
                {/* Email Row */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/10 transition-colors">
                  <div className="px-6 sm:px-10 lg:px-2 py-4 lg:py-0 lg:pt-[28px] lg:border-r border-slate-200 flex items-center lg:items-start justify-start lg:justify-center text-left lg:text-center">
                    <label
                      htmlFor="login-email"
                      className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer whitespace-nowrap"
                    >
                      Email
                    </label>
                  </div>
                  <div className="px-6 sm:px-10 lg:px-6 py-2 lg:py-3 flex flex-col justify-center w-full">
                    <input
                      id="login-email"
                      type="email"
                      autoComplete="email"
                      autoFocus
                      placeholder="name@lspu.edu.ph"
                      className="h-12 w-full rounded-none border-0 bg-transparent px-2 text-base focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-900"
                      value={email}
                      onChange={(event) => {
                        auth.clearError();
                        setEmail(event.target.value);
                        setEmailHint('');
                      }}
                      onBlur={handleEmailBlur}
                      required
                      aria-describedby={auth.error ? 'login-error' : undefined}
                    />
                    {emailHint && (
                      <p className="text-[11px] font-semibold text-[#f2c811] px-2 pt-1 transition-all">
                        {emailHint}
                      </p>
                    )}
                  </div>
                </div>

                {/* Password Row */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/10 transition-colors">
                  <div className="px-6 sm:px-10 lg:px-2 py-4 lg:py-0 lg:pt-[28px] lg:border-r border-slate-200 flex items-center lg:items-start justify-start lg:justify-center text-left lg:text-center">
                    <label
                      htmlFor="login-password"
                      className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-[#1b3b87] cursor-pointer whitespace-nowrap"
                    >
                      Password
                    </label>
                  </div>
                  <div className="px-6 sm:px-10 lg:px-6 py-2 lg:py-3 flex flex-col justify-center w-full">
                    <div className="relative flex items-center">
                      <input
                        id="login-password"
                        type={showPassword ? 'text' : 'password'}
                        autoComplete="current-password"
                        placeholder="••••••••"
                        className={`h-12 w-full rounded-none border-0 bg-transparent pl-2 pr-10 text-base focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-900 ${showPassword ? '' : 'tracking-widest'}`}
                        value={password}
                        onChange={(event) => {
                          auth.clearError();
                          setPassword(event.target.value);
                          setPasswordHint('');
                        }}
                        onBlur={handlePasswordBlur}
                        required
                        aria-describedby={auth.error ? 'login-error' : undefined}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-2 text-slate-400 hover:text-slate-600 focus:outline-none focus:text-[#1b3b87] cursor-pointer flex items-center justify-center p-1"
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? (
                          <EyeSlash className="size-5" aria-hidden="true" />
                        ) : (
                          <Eye className="size-5" aria-hidden="true" />
                        )}
                      </button>
                    </div>
                    <div className="flex justify-between items-center pt-2 pb-1">
                      <div className="text-[11px] font-semibold text-[#f2c811] px-2">
                        {passwordHint}
                      </div>
                      <button
                        ref={triggerRef}
                        type="button"
                        onClick={() => setShowResetDialog(true)}
                        className="text-[11px] font-bold text-[#1b3b87] hover:underline cursor-pointer opacity-60 hover:opacity-100 uppercase tracking-wider focus:outline-none focus:ring-2 focus:ring-[#1b3b87] transition-opacity ml-auto"
                      >
                        Reset Password
                      </button>
                    </div>
                  </div>
                </div>

                {/* Remember Row — label column is blank gutter; content aligns to input column */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-[#1b3b87]/10 transition-colors">
                  <div className="hidden lg:block lg:border-r border-slate-200 bg-slate-50/30" />
                  <div className="px-6 sm:px-10 lg:px-6 py-3 flex items-center gap-2.5">
                    <input
                      id="login-remember"
                      type="checkbox"
                      className="size-4 rounded-sm border-slate-300 text-[#1b3b87] focus:ring-2 focus:ring-[#1b3b87] cursor-pointer accent-[#1b3b87] shrink-0"
                      checked={rememberEmail}
                      onChange={(event) => setRememberEmail(event.target.checked)}
                    />
                    <label
                      htmlFor="login-remember"
                      className="text-xs font-medium text-slate-500 select-none cursor-pointer"
                    >
                      Remember my email address
                    </label>
                  </div>
                </div>

                {/* Error Row (Conditionally Rendered) */}
                {auth.error && (
                  <div
                    id="login-error"
                    role="alert"
                    className="border-b border-slate-200 bg-[#b91c1c]/10 px-6 sm:px-10 lg:px-14 py-5 flex items-start gap-3"
                  >
                    <ShieldWarning
                      className="size-4 shrink-0 mt-0.5 text-[#b91c1c]"
                      aria-hidden="true"
                    />
                    <span className="text-sm font-medium leading-relaxed text-[#b91c1c]">
                      {auth.error}
                    </span>
                  </div>
                )}

                {/* Action Row */}
                <div className="flex border-b border-slate-200">
                  <button
                    type="submit"
                    className="w-full h-14 rounded-none bg-[#1b3b87] hover:bg-[#1b3b87]/90 active:bg-[#1b3b87]/80 text-white font-bold text-[13px] tracking-[0.08em] uppercase transition-colors flex items-center justify-center gap-3 group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={isSubmitting || !email.trim() || password.length < 8}
                  >
                    {isSubmitting ? (
                      <span className="flex items-center gap-3">
                        <Spinner className="w-5 h-5 animate-spin opacity-80" />
                        Signing In
                      </span>
                    ) : (
                      <span className="flex items-center gap-3">
                        Sign In
                        <ArrowRight className="w-4 h-4 opacity-70 group-hover:opacity-100 group-hover:translate-x-1 transition-transform" />
                      </span>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Right Column (Gutter) */}
          <div className="hidden lg:block w-16 xl:w-24 border-l border-slate-200 shrink-0 bg-slate-50/30" />
        </div>

        {/* Bottom Margin (Structural) */}
        <div className="hidden lg:block h-16 border-t border-slate-200 w-full shrink-0 bg-slate-50/50 relative">
          <div className="absolute right-6 top-1/2 -translate-y-1/2 text-right">
            <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">
              © {new Date().getFullYear()} Laguna State Polytechnic University
            </p>
          </div>
        </div>
      </div>

      {/* Password Reset Modal */}
      <ResetPasswordModal isOpen={showResetDialog} onClose={() => setShowResetDialog(false)} />
    </div>
  );
}
