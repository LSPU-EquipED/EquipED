import type { ReactNode } from 'react';

export function AuthField({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="auth-form-field">
      <label htmlFor={id} className="auth-form-label">
        {label}
      </label>
      <div className="auth-form-input">{children}</div>
    </div>
  );
}
