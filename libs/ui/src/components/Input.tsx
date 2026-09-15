import React, { forwardRef, useId } from 'react';
import { cn } from '@/shared/components/utils';
import { INPUT_STYLES } from '@/shared/constants/theme';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, hint, error, id: idProp, required, ...props }, ref) => {
    const generatedId = useId();
    const id = idProp ?? (label ? generatedId : undefined);

    return (
      <div className="w-full">
        {label ? (
          <label htmlFor={id} className={INPUT_STYLES.label}>
            {label}
            {required ? <span className="ml-1 text-destructive">*</span> : null}
          </label>
        ) : null}
        <input
          ref={ref}
          id={id}
          required={required}
          className={cn(
            INPUT_STYLES.base,
            error && 'border-destructive focus-visible:ring-destructive',
            className,
          )}
          {...props}
        />
        {error ? (
          <p className={INPUT_STYLES.error} role="alert">
            {error}
          </p>
        ) : hint ? (
          <p className={INPUT_STYLES.hint}>{hint}</p>
        ) : null}
      </div>
    );
  },
);

Input.displayName = 'Input';
