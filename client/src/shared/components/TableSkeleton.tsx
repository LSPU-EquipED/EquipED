import type { ReactNode } from 'react';
import { Skeleton } from './Skeleton';
import { cn } from './utils';
import { TABLE_STYLES } from '@/shared/constants/theme';

export interface TableSkeletonColumn {
  label: string;
  headerClassName?: string;
  cellClassName?: string;
  skeletonClassName?: string;
}

export interface TableSkeletonProps {
  columns: TableSkeletonColumn[];
  rows?: number;
  ariaLabel?: string;
  className?: string;
  renderCell?: (column: TableSkeletonColumn, rowIndex: number, columnIndex: number) => ReactNode;
}

export function TableSkeleton({
  columns,
  rows = 5,
  ariaLabel = 'Loading table',
  className,
  renderCell,
}: TableSkeletonProps) {
  return (
    <div className={cn('overflow-x-auto', className)} role="status" aria-label={ariaLabel} aria-busy="true">
      <table className={TABLE_STYLES.table}>
        <thead className={TABLE_STYLES.thead}>
          <tr>
            {columns.map((column) => (
              <th key={column.label} scope="col" className={cn(TABLE_STYLES.th, column.headerClassName)}>
                <span className="sr-only">{column.label}</span>
                <Skeleton className="h-2.5 w-16" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={TABLE_STYLES.tbody}>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column, columnIndex) => (
                <td
                  key={`${column.label}-${rowIndex}`}
                  className={cn(TABLE_STYLES.td, column.cellClassName)}
                >
                  {renderCell?.(column, rowIndex, columnIndex) ?? (
                    <Skeleton className={column.skeletonClassName ?? 'h-4 w-full max-w-40'} />
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
