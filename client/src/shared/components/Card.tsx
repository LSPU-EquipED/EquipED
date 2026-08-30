import React, { forwardRef } from 'react';
import { cn } from '@/shared/components/utils';
import { CARD_STYLES, TYPOGRAPHY } from '@/shared/constants/theme';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'ledger' | 'flat';
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = 'ledger', ...props }, ref) => (
    <div
      ref={ref}
      className={cn(variant === 'ledger' ? CARD_STYLES.ledger : CARD_STYLES.flat, className)}
      {...props}
    />
  ),
);
Card.displayName = 'Card';

export const CardHeader = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn(CARD_STYLES.header, className)} {...props} />
  ),
);
CardHeader.displayName = 'CardHeader';

export const CardTitle = forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn(TYPOGRAPHY.headingMd, className)} {...props} />
  ),
);
CardTitle.displayName = 'CardTitle';

export const CardDescription = forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn(TYPOGRAPHY.labelMuted, className)} {...props} />
));
CardDescription.displayName = 'CardDescription';

export const CardContent = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn(CARD_STYLES.content, className)} {...props} />
  ),
);
CardContent.displayName = 'CardContent';

export const CardFooter = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn(CARD_STYLES.footer, className)} {...props} />
  ),
);
CardFooter.displayName = 'CardFooter';
