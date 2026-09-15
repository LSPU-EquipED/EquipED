import type { HTMLAttributes } from 'react';
import { cn } from './utils';

export interface SkeletonProps extends HTMLAttributes<HTMLSpanElement> {
  className?: string;
}

export function Skeleton({ className, 'aria-hidden': ariaHidden = true, ...props }: SkeletonProps) {
  return <span aria-hidden={ariaHidden} className={cn('skeleton-shimmer block rounded-sm', className)} {...props} />;
}
