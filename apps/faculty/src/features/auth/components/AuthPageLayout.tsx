import type { ReactNode } from 'react';
import { BrandHero } from '@equiped/auth';
import '../styles/auth-forms.css';

export function AuthPageLayout({
  children,
  wide = false,
}: {
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-surface font-sans selection:bg-primary selection:text-primary-foreground">
      <BrandHero />
      <main className="auth-page-main">
        <div className="auth-page-content">
          <div className={wide ? 'auth-form auth-form-wide' : 'auth-form'}>
            {children}
          </div>
        </div>
        <footer className="auth-page-footer">
          <span>
            © {new Date().getFullYear()} Laguna State Polytechnic University ·
            Santa Cruz Campus
          </span>
        </footer>
      </main>
    </div>
  );
}
