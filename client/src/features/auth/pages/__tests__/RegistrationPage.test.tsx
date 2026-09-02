// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { RegistrationPage } from '../RegistrationPage';
import { registrationApi } from '../../api/registration.api';

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, className }: { children: React.ReactNode; to: string; className?: string }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

vi.mock('../../api/registration.api', () => ({
  registrationApi: {
    start: vi.fn(),
    verify: vi.fn(),
    resend: vi.fn(),
  },
}));

describe('RegistrationPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders architectural ledger layout for registration with all intake fields', () => {
    render(<RegistrationPage />);

    expect(screen.getByRole('heading', { name: 'Create Faculty Account' })).toBeDefined();
    expect(screen.getByLabelText(/Full Name/i)).toBeDefined();
    expect(screen.getByLabelText(/LSPU Email/i)).toBeDefined();
    expect(screen.getByLabelText(/Faculty ID/i)).toBeDefined();
    expect(screen.getByLabelText(/Department/i)).toBeDefined();
    expect(screen.getByLabelText(/Program/i)).toBeDefined();
    expect(screen.getByLabelText(/^Password$/i)).toBeDefined();
    expect(
      screen.getByRole('button', { name: /Send Verification Code/i }),
    ).toBeDefined();
  });

  it('toggles password visibility with eye button', () => {
    render(<RegistrationPage />);

    const passwordInput = screen.getByLabelText(/^Password$/i) as HTMLInputElement;
    const toggleButton = screen.getByRole('button', { name: /Show password/i });

    expect(passwordInput.type).toBe('password');
    fireEvent.click(toggleButton);
    expect(passwordInput.type).toBe('text');
    expect(screen.getByRole('button', { name: /Hide password/i })).toBeDefined();
  });

  it('submits registration intake and transitions to email verification state', async () => {
    vi.mocked(registrationApi.start).mockResolvedValueOnce({
      registration_token: 'token-abc-123',
    });

    render(<RegistrationPage />);

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'Prof. Maria Santos' },
    });
    fireEvent.change(screen.getByLabelText(/LSPU Email/i), {
      target: { value: 'msantos@lspu.edu.ph' },
    });
    fireEvent.change(screen.getByLabelText(/Faculty ID/i), {
      target: { value: '2024-FAC-019' },
    });
    fireEvent.change(screen.getByLabelText(/Department/i), {
      target: { value: 'College of Computer Studies' },
    });
    fireEvent.change(screen.getByLabelText(/Program/i), {
      target: { value: 'BSCS' },
    });
    fireEvent.change(screen.getByLabelText(/^Password$/i), {
      target: { value: 'securePass123' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/i }));

    await waitFor(() => {
      expect(registrationApi.start).toHaveBeenCalledWith({
        name: 'Prof. Maria Santos',
        email: 'msantos@lspu.edu.ph',
        faculty_id: '2024-FAC-019',
        department: 'College of Computer Studies',
        program: 'BSCS',
        password: 'securePass123',
      });
      expect(screen.getByRole('heading', { name: 'Verify Your Email' })).toBeDefined();
      expect(screen.getByLabelText(/Verification Code/i)).toBeDefined();
    });
  });
});
