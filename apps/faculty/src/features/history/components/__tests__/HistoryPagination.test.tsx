// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HistoryPagination } from '../HistoryPagination';

afterEach(cleanup);

describe('HistoryPagination', () => {
  it('keeps the record range and row selector for a single page without inactive navigation', () => {
    const onPageSizeChange = vi.fn();
    render(
      <HistoryPagination
        page={1}
        pageSize={10}
        totalPages={1}
        total={2}
        onPageChange={vi.fn()}
        onPageSizeChange={onPageSizeChange}
      />,
    );
    expect(screen.getByText('1–2 of 2 evaluations')).toBeDefined();
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Rows per page' }));
    fireEvent.click(screen.getByRole('option', { name: '25 rows' }));
    expect(onPageSizeChange).toHaveBeenCalledWith(25);
  });

  it('navigates between pages and preserves the final page record range', () => {
    const onPageChange = vi.fn();
    const props = {
      page: 2,
      pageSize: 10,
      totalPages: 3,
      total: 23,
      onPageChange,
      onPageSizeChange: vi.fn(),
    };
    const { rerender } = render(<HistoryPagination {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Previous page' }));
    expect(onPageChange.mock.calls[0][0](2)).toBe(1);
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(onPageChange.mock.calls[1][0](2)).toBe(3);
    rerender(<HistoryPagination {...props} page={3} />);
    expect(screen.getByText('21–23 of 23 evaluations')).toBeDefined();
    expect(
      (screen.getByRole('button', { name: 'Next page' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    rerender(<HistoryPagination {...props} page={1} />);
    expect(
      (
        screen.getByRole('button', {
          name: 'Previous page',
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });
});
