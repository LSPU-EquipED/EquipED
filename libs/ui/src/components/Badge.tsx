import React from 'react';
import { cn } from '@/shared/components/utils';
import { STATUS_VARIANTS, type StatusVariant } from '@/shared/constants/theme';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: StatusVariant;
  withDot?: boolean;
}

export function Badge({
  className,
  variant = 'neutral',
  withDot = false,
  children,
  ...props
}: BadgeProps) {
  const styles = STATUS_VARIANTS[variant];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-xs px-2 py-0.5 text-xs font-semibold tracking-wide select-none',
        styles.container,
        className,
      )}
      {...props}
    >
      {withDot ? (
        <span className={cn('size-1.5 rounded-full', styles.dot)} aria-hidden="true" />
      ) : null}
      {children}
    </span>
  );
}
