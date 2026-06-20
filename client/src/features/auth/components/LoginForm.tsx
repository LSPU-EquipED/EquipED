import { useEffect, useState, useRef, type FormEvent } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useAuth } from '../hooks/useAuth';
import { ShieldAlert, ArrowRight, Loader2 } from 'lucide-react';

export function LoginForm() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState(() => localStorage.getItem('remembered_email') || '');
  const [password, setPassword] = useState('');
  const [rememberEmail, setRememberEmail] = useState(
    () => !!localStorage.getItem('remembered_email'),
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);

  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const modalRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (auth.status === 'authenticated') {
      const target = auth.user?.role === 'admin' ? '/admin' : '/dashboard';
      void navigate({ to: target });
    }
  }, [auth.status, auth.user, navigate]);

  useEffect(() => {
    if (showResetDialog) {
      const modal = modalRef.current;
      if (!modal) return;

      const focusableElements = modal.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusableElements.length > 0) {
        // Delay focus slightly to ensure render/transition is complete
        setTimeout(() => focusableElements[0].focus(), 50);
      }

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          setShowResetDialog(false);
          triggerRef.current?.focus();
          return;
        }

        if (e.key === 'Tab') {
          const focusables = Array.from(focusableElements);
          const first = focusables[0];
          const last = focusables[focusables.length - 1];

          if (e.shiftKey) {
            if (document.activeElement === first) {
              last.focus();
              e.preventDefault();
            }
          } else {
            if (document.activeElement === last) {
              first.focus();
              e.preventDefault();
            }
          }
        }
      };

      document.addEventListener('keydown', handleKeyDown);
      return () => {
        document.removeEventListener('keydown', handleKeyDown);
      };
    } else {
      triggerRef.current?.focus();
    }
  }, [showResetDialog]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    auth.clearError();
    setIsSubmitting(true);

    try {
      await auth.login({ email, password });
      if (rememberEmail) {
        localStorage.setItem('remembered_email', email);
      } else {
        localStorage.removeItem('remembered_email');
      }
    } catch {
      // Error state is normalized in the auth provider.
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-white font-sans selection:bg-primary selection:text-primary-foreground">
      {/* Left Pane: Brand Hero */}
      <div
        aria-hidden="true"
        className="relative w-full lg:w-5/12 bg-primary flex flex-col justify-between p-8 lg:p-12 text-primary-foreground overflow-hidden shrink-0 border-r border-primary-foreground/20"
      >
        {/* Subtle Academic Grid Pattern overlay for texture */}
        <div
          className="absolute inset-0 opacity-[0.08] pointer-events-none mix-blend-overlay"
          style={{
            backgroundImage: `linear-gradient(rgba(255, 255, 255, 1) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 1) 1px, transparent 1px)`,
            backgroundSize: '32px 32px',
          }}
        />

        <div className="relative z-10 flex flex-col gap-8">
          <div className="flex items-center gap-4 border-b border-primary-foreground/10 pb-6">
            <img
              src="/lspu-logo.png"
              alt="Laguna State Polytechnic University Logo"
              className="w-16 h-16 lg:w-20 lg:h-20 object-contain shrink-0"
            />
            <div>
              <h1 className="text-xl lg:text-2xl font-bold tracking-tight text-primary-foreground leading-snug">
                Laguna State
                <br />
                Polytechnic University
              </h1>
              <p className="text-xs font-semibold text-primary-foreground/80 tracking-wider uppercase mt-1">
                Santa Cruz Campus
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="text-lg font-bold text-primary-foreground uppercase tracking-wider">
              EquipED Workspace
            </h2>
            <p className="text-primary-foreground/70 text-sm leading-relaxed max-w-sm">
              An automated compliance workstation for Syllabus and Curriculum evaluations. Access is
              restricted to authorized faculty and administrative staff.
            </p>
          </div>
        </div>

        <div className="relative z-10 mt-16 lg:mt-0 flex items-start gap-3 border-t border-primary-foreground/10 pt-6">
          <ShieldAlert
            className="size-4 shrink-0 text-primary-foreground/80 mt-0.5"
            aria-hidden="true"
          />
          <p className="text-primary-foreground/80 text-xs font-medium max-w-sm leading-relaxed uppercase tracking-wider">
            Faculty Ledger System. Strictly for authorized institutional personnel. All access is
            monitored and logged.
          </p>
        </div>
      </div>

      {/* Right Pane: The Architectural Ledger */}
      <div className="w-full lg:w-7/12 bg-white flex flex-col min-h-0 border-l lg:border-l-0 border-slate-200">
        {/* Top Margin (Structural) */}
        <div className="hidden lg:block h-16 border-b border-slate-200 w-full shrink-0 bg-slate-50/50" />

        <div className="flex-1 flex flex-col lg:flex-row w-full h-full">
          {/* Left Column (Gutter) */}
          <div className="hidden lg:block w-16 xl:w-24 border-r border-slate-200 shrink-0 bg-slate-50/30" />

          {/* Main Content Column */}
          <div className="flex-1 flex flex-col justify-center border-r border-slate-200 relative py-8 lg:py-0">
            {/* Center Grid Block */}
            <div className="w-full border-y border-slate-200 bg-white relative">
              {/* Header Cell */}
              <div className="px-6 sm:px-10 lg:px-14 py-8 lg:py-10 border-b border-slate-200 bg-slate-50/30">
                <h2 className="text-2xl lg:text-3xl font-bold tracking-tight text-slate-900 mb-2">
                  Sign In
                </h2>
                <p className="text-sm text-slate-600 font-medium">
                  Authenticate with your university credentials.
                </p>
              </div>

              {/* Ledger Form */}
              <form onSubmit={handleSubmit} className="flex flex-col">
                {/* Email Row */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-blue-50/30 transition-colors">
                  <div className="px-6 sm:px-10 lg:px-14 py-4 lg:py-5 lg:border-r border-slate-200 flex items-center">
                    <Label
                      htmlFor="login-email"
                      className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-primary"
                    >
                      Email
                    </Label>
                  </div>
                  <div className="px-6 sm:px-10 lg:px-14 py-2 lg:py-3 flex items-center">
                    <Input
                      id="login-email"
                      type="email"
                      autoComplete="email"
                      autoFocus
                      placeholder="name@lspu.edu.ph"
                      className="h-12 w-full rounded-none border-0 bg-transparent px-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 placeholder:text-slate-400 font-semibold text-slate-900"
                      value={email}
                      onChange={(event) => {
                        auth.clearError();
                        setEmail(event.target.value);
                      }}
                      required
                      aria-describedby={auth.error ? 'login-error' : undefined}
                    />
                  </div>
                </div>

                {/* Password Row */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-blue-50/30 transition-colors">
                  <div className="px-6 sm:px-10 lg:px-14 py-4 lg:py-5 lg:border-r border-slate-200 flex items-center">
                    <Label
                      htmlFor="login-password"
                      className="text-xs font-bold uppercase tracking-wider text-slate-500 group-focus-within:text-primary"
                    >
                      Password
                    </Label>
                  </div>
                  <div className="px-6 sm:px-10 lg:px-14 py-2 lg:py-3 flex flex-col">
                    <Input
                      id="login-password"
                      type="password"
                      autoComplete="current-password"
                      placeholder="••••••••"
                      className="h-12 w-full rounded-none border-0 bg-transparent px-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 placeholder:text-slate-400 font-semibold text-slate-900 tracking-widest"
                      value={password}
                      onChange={(event) => {
                        auth.clearError();
                        setPassword(event.target.value);
                      }}
                      required
                      aria-describedby={auth.error ? 'login-error' : undefined}
                    />
                    <div className="flex justify-end pt-2 pb-1">
                      <button
                        ref={triggerRef}
                        type="button"
                        onClick={() => setShowResetDialog(true)}
                        className="text-[11px] font-bold text-primary hover:underline cursor-pointer opacity-60 hover:opacity-100 uppercase tracking-wider focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 transition-opacity"
                      >
                        Reset Password
                      </button>
                    </div>
                  </div>
                </div>

                {/* Remember Row — label column is blank gutter; content aligns to input column */}
                <div className="grid grid-cols-1 lg:grid-cols-[140px_1fr] border-b border-slate-200 group focus-within:bg-blue-50/30 transition-colors">
                  <div className="hidden lg:block lg:border-r border-slate-200 bg-slate-50/30" />
                  <div className="px-6 sm:px-10 lg:px-14 py-3 flex items-center gap-2.5">
                    <input
                      id="login-remember"
                      type="checkbox"
                      className="size-4 rounded-sm border-slate-300 text-primary focus:ring-2 focus:ring-primary focus:ring-offset-1 cursor-pointer accent-primary shrink-0"
                      checked={rememberEmail}
                      onChange={(event) => setRememberEmail(event.target.checked)}
                    />
                    <Label
                      htmlFor="login-remember"
                      className="text-xs font-medium text-slate-500 select-none cursor-pointer"
                    >
                      Remember my email address
                    </Label>
                  </div>
                </div>

                {/* Error Row (Conditionally Rendered) */}
                {auth.error && (
                  <div
                    id="login-error"
                    role="alert"
                    className="border-b border-slate-200 bg-red-50/80 px-6 sm:px-10 lg:px-14 py-5 flex items-start gap-3 animate-in fade-in"
                  >
                    <ShieldAlert
                      className="size-4 shrink-0 mt-0.5 text-red-600"
                      aria-hidden="true"
                    />
                    <span className="text-sm font-medium leading-relaxed text-red-900">
                      {auth.error}
                    </span>
                  </div>
                )}

                {/* Action Row */}
                <div className="flex">
                  <Button
                    type="submit"
                    className="w-full h-16 rounded-none bg-primary hover:bg-primary/90 active:bg-primary/80 text-primary-foreground font-bold text-[13px] tracking-[0.1em] uppercase transition-colors flex items-center justify-center gap-3 group cursor-pointer"
                    disabled={isSubmitting || !email.trim() || password.length < 8}
                  >
                    {isSubmitting ? (
                      <span className="flex items-center gap-3">
                        <Loader2 className="w-5 h-5 animate-spin opacity-80" />
                        Signing In
                      </span>
                    ) : (
                      <span className="flex items-center gap-3">
                        Sign In
                        <ArrowRight className="w-4 h-4 opacity-70 group-hover:opacity-100 group-hover:translate-x-1 transition-transform" />
                      </span>
                    )}
                  </Button>
                </div>
              </form>
            </div>


          </div>

          {/* Right Column (Gutter) */}
          <div className="hidden lg:block w-16 xl:w-24 shrink-0 bg-slate-50/30" />
        </div>

        {/* Bottom Margin (Structural) */}
        <div className="hidden lg:block h-16 border-t border-slate-200 w-full shrink-0 bg-slate-50/50 relative">
          <div className="absolute right-6 top-1/2 -translate-y-1/2 text-right">
            <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">
              © {new Date().getFullYear()} LSPU
            </p>
          </div>
        </div>
      </div>

      {/* Password Reset Modal */}
      {showResetDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-dialog-title"
        >
          <div
            ref={modalRef}
            className="w-full max-w-md bg-white border border-slate-200 p-6 sm:p-8 rounded-none shadow-none relative"
          >
            <h3 id="reset-dialog-title" className="text-lg font-bold text-slate-900 mb-3 uppercase tracking-wider">
              Password Reset Request
            </h3>
            <p className="text-sm text-slate-600 leading-relaxed mb-6 font-medium">
              Password resets must be requested directly through the LSPU IT Support Office (ITSO).
              Please visit their office or contact them via official channels to recover your
              credentials.
            </p>
            <Button
              type="button"
              className="w-full h-12 rounded-none bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-[13px] tracking-[0.1em] uppercase transition-colors cursor-pointer"
              onClick={() => setShowResetDialog(false)}
            >
              Close
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
