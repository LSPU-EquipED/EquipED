// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ConfirmationModal } from '../ConfirmationModal';

describe('ConfirmationModal', () => {
  afterEach(cleanup);

  it('does not render when isOpen is false', () => {
    render(
      <ConfirmationModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Delete Item"
        description="Are you sure?"
      />,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders title, description, and buttons when open', () => {
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Delete Draft Revision"
        description="Are you sure you want to delete this draft revision?"
        confirmLabel="Yes, Delete Draft"
        cancelLabel="Cancel"
      />,
    );

    expect(screen.getByRole('dialog')).toBeDefined();
    expect(screen.getByText('Delete Draft Revision')).toBeDefined();
    expect(
      screen.getByText('Are you sure you want to delete this draft revision?'),
    ).toBeDefined();
    expect(screen.getByRole('button', { name: 'Yes, Delete Draft' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDefined();
  });

  it('calls onConfirm when confirm button is clicked', () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={onConfirm}
        title="Delete Item"
        description="Are you sure?"
        confirmLabel="Confirm Delete"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Confirm Delete' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when cancel button or close X is clicked', () => {
    const onClose = vi.fn();
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={onClose}
        onConfirm={vi.fn()}
        title="Delete Item"
        description="Are you sure?"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText('Close dialog'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
