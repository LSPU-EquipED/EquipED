import type { ComponentPropsWithoutRef } from 'react';
import { Eye, EyeSlash } from '@phosphor-icons/react';

type AuthPasswordInputProps = Omit<
  ComponentPropsWithoutRef<'input'>,
  'type' | 'className'
> & {
  visible: boolean;
  onVisibilityChange: (visible: boolean) => void;
};

export function AuthPasswordInput({
  visible,
  onVisibilityChange,
  ...inputProps
}: AuthPasswordInputProps) {
  return (
    <div className="auth-form-password">
      <input
        {...inputProps}
        type={visible ? 'text' : 'password'}
        className="auth-form-control"
      />
      <button
        type="button"
        onClick={() => onVisibilityChange(!visible)}
        className="auth-form-reveal"
        aria-label={visible ? 'Hide password' : 'Show password'}
        title={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
      >
        {visible ? (
          <EyeSlash className="size-4" aria-hidden="true" />
        ) : (
          <Eye className="size-4" aria-hidden="true" />
        )}
      </button>
    </div>
  );
}
