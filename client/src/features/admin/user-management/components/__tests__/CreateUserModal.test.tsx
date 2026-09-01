// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { CreateUserModal } from '../CreateUserModal';

const mockCreateUserMutateAsync = vi.fn();

vi.mock('../../hooks/useAdminUsers', () => ({
  useCreateUser: () => ({
    mutateAsync: mockCreateUserMutateAsync,
    isPending: false,
  }),
}));

describe('CreateUserModal', () => {
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders nothing when open is false', () => {
    const { container } = render(
      <CreateUserModal open={false} onOpenChange={mockOnOpenChange} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('enforces required field validation for name, email, and password', async () => {
    render(<CreateUserModal open={true} onOpenChange={mockOnOpenChange} />);

    const submitBtn = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitBtn);

    expect(screen.getByText('Name is required.')).toBeDefined();
    expect(screen.getByText('Email is required.')).toBeDefined();
    expect(screen.getByText('Password is required.')).toBeDefined();
    expect(mockCreateUserMutateAsync).not.toHaveBeenCalled();
  });

  it('enforces official @lspu.edu.ph email domain validation', async () => {
    render(<CreateUserModal open={true} onOpenChange={mockOnOpenChange} />);

    fireEvent.change(screen.getByLabelText(/Full Name/i), { target: { value: 'Dr. Santos' } });
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'santos@gmail.com' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'ValidPass123' } });

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(
      screen.getByText('Please use your official @lspu.edu.ph email address.'),
    ).toBeDefined();
    expect(mockCreateUserMutateAsync).not.toHaveBeenCalled();
  });

  it('enforces password lower bound (minimum 8 characters)', async () => {
    render(<CreateUserModal open={true} onOpenChange={mockOnOpenChange} />);

    fireEvent.change(screen.getByLabelText(/Full Name/i), { target: { value: 'Dr. Santos' } });
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'santos@lspu.edu.ph' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'short' } });

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(screen.getByText('Password must be at least 8 characters.')).toBeDefined();
    expect(mockCreateUserMutateAsync).not.toHaveBeenCalled();
  });

  it('enforces password upper bound (maximum 256 characters per spec)', async () => {
    render(<CreateUserModal open={true} onOpenChange={mockOnOpenChange} />);

    const oversizedPassword = 'a'.repeat(257);
    fireEvent.change(screen.getByLabelText(/Full Name/i), { target: { value: 'Dr. Santos' } });
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'santos@lspu.edu.ph' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: oversizedPassword } });

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(screen.getByText('Password must be 256 characters or fewer.')).toBeDefined();
    expect(mockCreateUserMutateAsync).not.toHaveBeenCalled();
  });

  it('submits valid form data and closes modal on success', async () => {
    mockCreateUserMutateAsync.mockResolvedValueOnce({
      user_id: 'user-new-1',
      name: 'Dr. Santos',
      email: 'santos@lspu.edu.ph',
      role: 'faculty',
      is_active: false,
      account_status: 'pending',
      created_at: '2026-09-01T12:00:00Z',
    });

    render(<CreateUserModal open={true} onOpenChange={mockOnOpenChange} />);

    fireEvent.change(screen.getByLabelText(/Full Name/i), { target: { value: 'Dr. Santos' } });
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'Santos@LSPU.EDU.PH' } });
    fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'SecurePass2026!' } });

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    await waitFor(() => {
      expect(mockCreateUserMutateAsync).toHaveBeenCalledWith({
        name: 'Dr. Santos',
        email: 'santos@lspu.edu.ph',
        password: 'SecurePass2026!',
        role: 'faculty',
      });
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
