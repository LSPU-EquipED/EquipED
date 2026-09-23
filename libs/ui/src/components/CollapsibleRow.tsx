import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../utils';

export interface CollapsibleRowProps extends HTMLAttributes<HTMLTableRowElement> {
  isExpanded: boolean;
  colSpan: number;
  children: ReactNode;
  cellClassName?: string;
  innerClassName?: string;
}

/**
 * CollapsibleRow renders an animated table drawer row compliant with
 * EquipED functional motion tokens and WCAG 2.2 reduced-motion standards.
 */
export function CollapsibleRow({
  isExpanded,
  colSpan,
  children,
  className,
  cellClassName,
  innerClassName,
  ...props
}: CollapsibleRowProps) {
  return (
    <tr
      className={cn(
        'border-b border-border/80 bg-surface-subtle/30 transition-[background-color,border-color] duration-200',
        !isExpanded && 'border-b-0',
        className,
      )}
      {...props}
    >
      <td colSpan={colSpan} className={cn('p-0', cellClassName)}>
        <div
          className={cn(
            'animate-ledger-collapse',
            isExpanded
              ? 'animate-ledger-collapse-expanded'
              : 'animate-ledger-collapse-collapsed',
          )}
          aria-hidden={!isExpanded}
          {...(!isExpanded ? { inert: '' } : {})}
        >
          <div className="min-h-0 overflow-hidden">
            <div className={innerClassName}>{children}</div>
          </div>
        </div>
      </td>
    </tr>
  );
}
