import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useAuth } from '../hooks/useAuth';

export function LoginForm() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (auth.status === 'authenticated') {
      const target = auth.user?.role === 'admin' ? '/admin' : '/dashboard';
      void navigate({ to: target });
    }
  }, [auth.status, auth.user, navigate]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    auth.clearError();
    setIsSubmitting(true);

    try {
      await auth.login({ email, password });
    } catch {
      // Error state is normalized in the auth provider.
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="grid min-h-screen place-items-center bg-background px-6 py-10 text-foreground">
      <form onSubmit={handleSubmit} className="grid w-full max-w-md gap-6 rounded-2xl border bg-card p-8 shadow-sm">
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Sign in</p>
          <h1 className="text-3xl font-semibold">Access EquipEd</h1>
          <p className="text-sm leading-6 text-muted-foreground">
            Use your server-managed account to access the document dashboard and upload workspace.
          </p>
        </div>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="login-email">Email</Label>
            <Input
              id="login-email"
              type="email"
              autoComplete="email"
              placeholder="name@lspu.edu.ph"
              value={email}
              onChange={(event) => {
                auth.clearError();
                setEmail(event.target.value);
              }}
              required
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="login-password">Password</Label>
            <Input
              id="login-password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(event) => {
                auth.clearError();
                setPassword(event.target.value);
              }}
              required
            />
          </div>
        </div>

        {auth.error ? <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{auth.error}</div> : null}

        <Button type="submit" size="lg" disabled={isSubmitting || !email.trim() || password.length < 8}>
          {isSubmitting ? 'Signing in…' : 'Continue'}
        </Button>

        <p className="text-sm text-muted-foreground">Sessions use an HTTP-only cookie. Closing the browser does not sign you out automatically.</p>
      </form>
    </section>
  );
}
