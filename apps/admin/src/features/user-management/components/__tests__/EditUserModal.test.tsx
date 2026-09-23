// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { EditUserModal } from '../EditUserModal';
import type { AdminUserResponse } from '../../types';

const mockUpdateUserMutateAsync = vi.fn();

vi.mock('../../hooks/useAdminUsers', () => ({
  useUpdateUser: () => ({
    mutateAsync: mockUpdateUserMutateAsync,
    isPending: false,
  }),
}));

const mockUser: AdminUserResponse = {
  user_id: 'user-123',
  name: 'Prof. Cruz',
  email: 'cruz@lspu.edu.ph',
  role: 'faculty',
  is_active: true,
  account_status: 'approved',
  evaluator_permissions: [],
  created_at: '2026-01-01T00:00:00Z',
};

describe('EditUserModal', () => {
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
      <EditUserModal open={false} user={mockUser} onOpenChange={mockOnOpenChange} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when user is null', () => {
    const { container } = render(
      <EditUserModal open={true} user={null} onOpenChange={mockOnOpenChange} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('enforces required field validation for email', async () => {
    render(<EditUserModal open={true} user={mockUser} onOpenChange={mockOnOpenChange} />);

    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: '   ' } });

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(screen.getByText('Email is required.')).toBeDefined();
    expect(mockUpdateUserMutateAsync).not.toHaveBeenCalled();
  });

  it('enforces email max length of 40 characters', async () => {
    render(<EditUserModal open={true} user={mockUser} onOpenChange={mockOnOpenChange} />);

    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: 'a'.repeat(29) + '@lspu.edu.ph' },
    });

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(screen.getByText('Email must be 40 characters or fewer.')).toBeDefined();
    expect(mockUpdateUserMutateAsync).not.toHaveBeenCalled();
  });

  it('enforces official @lspu.edu.ph email domain validation', async () => {
    render(<EditUserModal open={true} user={mockUser} onOpenChange={mockOnOpenChange} />);

    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: 'cruz@gmail.com' },
    });

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(
      screen.getByText('Please use your official @lspu.edu.ph email address.'),
    ).toBeDefined();
    expect(mockUpdateUserMutateAsync).not.toHaveBeenCalled();
  });

  it('submits normalized email and closes modal on success', async () => {
    mockUpdateUserMutateAsync.mockResolvedValueOnce({
      ...mockUser,
      name: 'Prof. Cruz Updated',
      email: 'cruz.updated@lspu.edu.ph',
    });

    render(<EditUserModal open={true} user={mockUser} onOpenChange={mockOnOpenChange} />);

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'Prof. Cruz Updated' },
    });
    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: '  Cruz.Updated@LSPU.EDU.PH  ' },
    });

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(mockUpdateUserMutateAsync).toHaveBeenCalledWith({
        userId: 'user-123',
        body: {
          name: 'Prof. Cruz Updated',
          email: 'cruz.updated@lspu.edu.ph',
          evaluator_permissions: [],
        },
      });
      expect(mockOnOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
