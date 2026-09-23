// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import React from 'react';
import { ConfirmationModal } from '../ConfirmationModal';

describe('ConfirmationModal', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <ConfirmationModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Delete User"
        description="Are you sure you want to delete this user?"
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders title, description, and action buttons when open', () => {
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Delete User Account"
        description="This action cannot be undone."
        confirmLabel="Confirm Deletion"
        cancelLabel="Keep Account"
      />,
    );

    expect(screen.getByRole('dialog', { name: 'Delete User Account' })).toBeDefined();
    expect(screen.getByText('This action cannot be undone.')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Confirm Deletion' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Keep Account' })).toBeDefined();
  });

  it('does not render a duplicate close (X) button', () => {
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Confirm Action"
        description="Proceed with action?"
      />,
    );

    // Cancel is the sole dismissal action; no duplicate X close button
    expect(screen.queryByRole('button', { name: /close/i })).toBeNull();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDefined();
  });

  it('calls onConfirm when confirm button is clicked', async () => {
    const handleConfirm = vi.fn();
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={handleConfirm}
        title="Suspend User"
        description="Suspend this user account?"
        confirmLabel="Suspend"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Suspend' }));
    expect(handleConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when cancel button is clicked', () => {
    const handleClose = vi.fn();
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={handleClose}
        onConfirm={vi.fn()}
        title="Confirm Action"
        description="Proceed with action?"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('closes on Escape key press', () => {
    const handleClose = vi.fn();
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={handleClose}
        onConfirm={vi.fn()}
        title="Confirm Action"
        description="Proceed with action?"
      />,
    );

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('moves focus into dialog (cancel button) when opened', async () => {
    vi.useFakeTimers();
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Confirm Focus"
        description="Proceed?"
      />,
    );

    // flush requestAnimationFrame
    vi.advanceTimersByTime(20);

    const cancelButton = screen.getByRole('button', { name: 'Cancel' });
    expect(document.activeElement).toBe(cancelButton);
    vi.useRealTimers();
  });

  it('traps Tab navigation in a forward cycle and Shift+Tab backward cycle', async () => {
    vi.useFakeTimers();
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Confirm Trap"
        description="Proceed?"
        cancelLabel="Cancel Action"
        confirmLabel="Confirm Action"
      />,
    );

    vi.advanceTimersByTime(20);

    const cancelButton = screen.getByRole('button', { name: 'Cancel Action' });
    const confirmButton = screen.getByRole('button', { name: 'Confirm Action' });

    expect(document.activeElement).toBe(cancelButton);

    // Tab forward from cancel to confirm
    fireEvent.keyDown(window, { key: 'Tab' });
    // In browser Tab advances to next, but when at last element or wrapping:
    confirmButton.focus();
    expect(document.activeElement).toBe(confirmButton);

    // Tab forward from last element (confirm) wraps to first (cancel)
    const eventTab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    window.dispatchEvent(eventTab);
    expect(eventTab.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(cancelButton);

    // Shift+Tab backward from first element (cancel) wraps to last (confirm)
    const eventShiftTab = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
    window.dispatchEvent(eventShiftTab);
    expect(eventShiftTab.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(confirmButton);

    vi.useRealTimers();
  });

  it('restores prior trigger focus when closed and after unmount', async () => {
    vi.useFakeTimers();
    const triggerButton = document.createElement('button');
    triggerButton.textContent = 'Open Modal';
    document.body.appendChild(triggerButton);
    triggerButton.focus();
    expect(document.activeElement).toBe(triggerButton);

    const { rerender } = render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Delete User"
        description="Are you sure?"
      />,
    );

    vi.advanceTimersByTime(20);
    const cancelButton = screen.getByRole('button', { name: 'Cancel' });
    expect(document.activeElement).toBe(cancelButton);

    // Close the modal
    rerender(
      <ConfirmationModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Delete User"
        description="Are you sure?"
      />,
    );

    // Focus restored immediately upon isOpen becoming false
    expect(document.activeElement).toBe(triggerButton);

    // Wait out animation duration (180ms) for unmount
    vi.advanceTimersByTime(200);
    expect(document.activeElement).toBe(triggerButton);

    document.body.removeChild(triggerButton);
    vi.useRealTimers();
  });

  it('prevents Escape dismissal and handles disabled/pending state appropriately', () => {
    const handleClose = vi.fn();
    render(
      <ConfirmationModal
        isOpen={true}
        onClose={handleClose}
        onConfirm={vi.fn()}
        title="Deleting User"
        description="Please wait..."
        isPending={true}
      />,
    );

    const cancelButton = screen.getByRole('button', { name: 'Cancel' });
    const confirmButton = screen.getByRole('button', { name: /processing/i });

    expect(cancelButton.hasAttribute('disabled')).toBe(true);
    expect(confirmButton.hasAttribute('disabled')).toBe(true);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose).not.toHaveBeenCalled();
  });

  it('hands focus and keyboard control back to the underlying dialog during top-dialog exit', () => {
    vi.useFakeTimers();
    const trigger = document.createElement('button');
    document.body.appendChild(trigger);
    trigger.focus();
    const closeTop = vi.fn();
    const closeBottom = vi.fn();
    const { rerender } = render(
      <>
        <ConfirmationModal isOpen onClose={closeBottom} onConfirm={vi.fn()} title="Bottom" description="Bottom" />
        <ConfirmationModal isOpen onClose={closeTop} onConfirm={vi.fn()} title="Top" description="Top" />
      </>,
    );
    const bottom = screen.getByRole('dialog', { name: 'Bottom' });
    const top = screen.getByRole('dialog', { name: 'Top' });
    const bottomCancel = within(bottom).getByRole('button', { name: 'Cancel' });
    const topCancel = within(top).getByRole('button', { name: 'Cancel' });
    topCancel.focus();
    rerender(
      <>
        <ConfirmationModal isOpen onClose={closeBottom} onConfirm={vi.fn()} title="Bottom" description="Bottom" />
        <ConfirmationModal isOpen={false} onClose={closeTop} onConfirm={vi.fn()} title="Top" description="Top" />
      </>,
    );
    expect(document.activeElement).toBe(bottomCancel);
    expect(top.getAttribute('aria-hidden')).toBe('true');
    fireEvent.keyDown(window, { key: 'Tab' });
    expect(document.activeElement).not.toBe(topCancel);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(closeBottom).toHaveBeenCalledTimes(1);

    rerender(
      <>
        <ConfirmationModal isOpen={false} onClose={closeBottom} onConfirm={vi.fn()} title="Bottom" description="Bottom" />
        <ConfirmationModal isOpen={false} onClose={closeTop} onConfirm={vi.fn()} title="Top" description="Top" />
      </>,
    );
    expect(document.activeElement).toBe(trigger);
    document.body.removeChild(trigger);
    vi.useRealTimers();
  });

  it('handles nested/multiple dialogs reasonably by routing keyboard events only to the active top modal', () => {
    const handleClose1 = vi.fn();
    const handleClose2 = vi.fn();

    render(
      <div>
        <ConfirmationModal
          isOpen={true}
          onClose={handleClose1}
          onConfirm={vi.fn()}
          title="Modal 1"
          description="Description 1"
        />
        <ConfirmationModal
          isOpen={true}
          onClose={handleClose2}
          onConfirm={vi.fn()}
          title="Modal 2"
          description="Description 2"
        />
      </div>,
    );

    // Escape should only dismiss the topmost modal (Modal 2)
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose2).toHaveBeenCalledTimes(1);
    expect(handleClose1).not.toHaveBeenCalled();
  });

  it('displays fallback error message in alert role when onConfirm rejects without an external error prop', async () => {
    const handleConfirm = vi.fn().mockRejectedValue(new Error('Network failure'));

    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={handleConfirm}
        title="Delete Item"
        description="Are you sure you want to delete this item?"
      />,
    );

    expect(screen.queryByRole('alert')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toBeDefined();
    expect(alert.textContent).toContain('An error occurred while processing this action. Please try again.');
  });

  it('prioritizes caller error prop over fallback error when onConfirm rejects', async () => {
    const handleConfirm = vi.fn().mockRejectedValue(new Error('Network failure'));

    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={handleConfirm}
        title="Delete Item"
        description="Are you sure you want to delete this item?"
        error="Custom caller error"
      />,
    );

    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('Custom caller error');

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    // Confirm that caller error is still displayed and not replaced by fallback
    expect(screen.getByRole('alert').textContent).toContain('Custom caller error');
    expect(screen.getByRole('alert').textContent).not.toContain('An error occurred while processing this action');
  });

  it('clears fallback error on retry and when modal closes/reopens', async () => {
    let shouldReject = true;
    const handleConfirm = vi.fn().mockImplementation(() => {
      if (shouldReject) {
        return Promise.reject(new Error('First failure'));
      }
      return Promise.resolve();
    });

    const { rerender } = render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={handleConfirm}
        title="Delete Item"
        description="Are you sure you want to delete this item?"
      />,
    );

    // Initial click fails -> shows fallback error
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(await screen.findByRole('alert')).toBeDefined();

    // Second click (retry) -> clears fallback error while executing
    shouldReject = false;
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(screen.queryByRole('alert')).toBeNull();
    await screen.findByRole('button', { name: 'Delete' });

    // Third click fails again -> shows fallback error
    shouldReject = true;
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(await screen.findByRole('alert')).toBeDefined();
    await screen.findByRole('button', { name: 'Delete' });

    // Closing and reopening clears fallback error
    rerender(
      <ConfirmationModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={handleConfirm}
        title="Delete Item"
        description="Are you sure you want to delete this item?"
      />,
    );

    rerender(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={handleConfirm}
        title="Delete Item"
        description="Are you sure you want to delete this item?"
      />,
    );

    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('prevents duplicate submits while confirmation promise is pending', async () => {
    let resolvePromise!: () => void;
    const pendingPromise = new Promise<void>((resolve) => {
      resolvePromise = resolve;
    });
    const handleConfirm = vi.fn().mockImplementation(() => pendingPromise);

    render(
      <ConfirmationModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={handleConfirm}
        title="Delete Item"
        description="Are you sure you want to delete this item?"
      />,
    );

    const deleteButton = screen.getByRole('button', { name: 'Delete' });
    fireEvent.click(deleteButton);
    expect(handleConfirm).toHaveBeenCalledTimes(1);

    // Buttons should now be disabled and in processing state
    expect(deleteButton.hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: /processing/i })).toBeDefined();

    // Click again while still pending
    fireEvent.click(deleteButton);
    expect(handleConfirm).toHaveBeenCalledTimes(1);

    resolvePromise();
  });
});
