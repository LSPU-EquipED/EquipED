import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../utils';
import { SHELL_STYLES } from '../theme/tokens';

export interface PageContainerProps extends HTMLAttributes<HTMLElement> {
  as?: 'section' | 'main' | 'div';
  className?: string;
  children?: ReactNode;
}

export function PageContainer({
  as: Component = 'section',
  className,
  children,
  ...props
}: PageContainerProps) {
  return (
    <Component className={cn(SHELL_STYLES.container, className)} {...props}>
      {children}
    </Component>
  );
}
