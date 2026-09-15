// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { Skeleton } from '../Skeleton';
import { TableSkeleton } from '../TableSkeleton';

describe('Loading primitives', () => {
  it('keeps decorative skeletons hidden from assistive technology by default', () => {
    const { container } = render(<Skeleton className="h-4 w-20" />);
    const skeleton = container.querySelector('span.skeleton-shimmer');

    expect(skeleton?.getAttribute('aria-hidden')).toBe('true');
  });

  it('announces table loading while preserving the table column structure', () => {
    render(
      <TableSkeleton
        ariaLabel="Loading faculty records"
        rows={3}
        columns={[
          { label: 'Faculty', skeletonClassName: 'h-4 w-32' },
          { label: 'Status', skeletonClassName: 'h-4 w-20' },
        ]}
      />,
    );

    const status = screen.getByRole('status', { name: 'Loading faculty records' });
    expect(status.getAttribute('aria-busy')).toBe('true');
    expect(within(status).getAllByRole('columnheader')).toHaveLength(2);
    expect(within(status).getAllByRole('row')).toHaveLength(4);
    expect(within(status).getAllByRole('columnheader')[0].getAttribute('scope')).toBe('col');
  });
});
