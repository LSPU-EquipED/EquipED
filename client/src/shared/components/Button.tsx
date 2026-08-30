import React, { forwardRef } from 'react';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES } from '@/shared/constants/theme';

export type ButtonVariant = keyof typeof BUTTON_STYLES.variants;
export type ButtonSize = keyof typeof BUTTON_STYLES.sizes;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled,
      children,
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          BUTTON_STYLES.base,
          BUTTON_STYLES.variants[variant],
          BUTTON_STYLES.sizes[size],
          className,
        )}
        {...props}
      >
        {isLoading ? (
          <span
            className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
            aria-hidden="true"
          />
        ) : null}
        {children}
      </button>
    );
  },
);

Button.displayName = 'Button';
