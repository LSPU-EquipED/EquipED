// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { RegistrationPage } from '../RegistrationPage';
import { registrationApi } from '../../api/registration.api';

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    to,
    className,
  }: {
    children: React.ReactNode;
    to: string;
    className?: string;
  }) => (
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

  it('renders registration with all intake fields', () => {
    render(<RegistrationPage />);

    expect(
      screen.getByRole('heading', { name: /Create faculty account/i }),
    ).toBeDefined();
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

    const passwordInput = screen.getByLabelText(
      /^Password$/i,
    ) as HTMLInputElement;
    const toggleButton = screen.getByRole('button', { name: /Show password/i });

    expect(passwordInput.type).toBe('password');
    fireEvent.click(toggleButton);
    expect(passwordInput.type).toBe('text');
    expect(
      screen.getByRole('button', { name: /Hide password/i }),
    ).toBeDefined();
  });

  it('preserves intake, resend, verification errors, and pending approval', async () => {
    vi.mocked(registrationApi.start).mockResolvedValueOnce({
      registration_token: 'token-abc-123',
      email: 'maria.santos@lspu.edu.ph',
      message: 'Verification code sent',
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

    fireEvent.click(
      screen.getByRole('button', { name: /Send Verification Code/i }),
    );

    await waitFor(() => {
      expect(registrationApi.start).toHaveBeenCalledWith({
        name: 'Prof. Maria Santos',
        email: 'msantos@lspu.edu.ph',
        faculty_id: '2024-FAC-019',
        department: 'College of Computer Studies',
        program: 'BSCS',
        password: 'securePass123',
      });
      expect(
        screen.getByRole('heading', { name: /Verify your email/i }),
      ).toBeDefined();
      expect(screen.getByLabelText(/Verification Code/i)).toBeDefined();
    });

    vi.mocked(registrationApi.resend).mockResolvedValueOnce({
      registration_token: 'token-abc-123',
      email: 'msantos@lspu.edu.ph',
      message: 'Sent',
    });
    fireEvent.click(screen.getByRole('button', { name: /Resend code/i }));
    await waitFor(() => {
      expect(registrationApi.resend).toHaveBeenCalledWith('token-abc-123');
      expect(
        (
          screen.getByRole('button', {
            name: /Resend code/i,
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(false);
    });
    expect(
      (
        screen.getByRole('button', {
          name: /Verify email/i,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    fireEvent.change(screen.getByLabelText(/Verification code/i), {
      target: { value: '123456' },
    });
    vi.mocked(registrationApi.verify).mockRejectedValueOnce(
      new Error('Code expired'),
    );
    fireEvent.click(screen.getByRole('button', { name: /Verify email/i }));
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain('Code expired'),
    );
    expect(
      screen
        .getByLabelText(/Verification code/i)
        .getAttribute('aria-describedby'),
    ).toBe('registration-error');
    vi.mocked(registrationApi.verify).mockResolvedValueOnce({
      status: 'pending_approval',
      message: 'Verified',
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify email/i }));
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: /Registration submitted/i }),
      ).toBeDefined(),
    );
    expect(registrationApi.verify).toHaveBeenLastCalledWith(
      'token-abc-123',
      '123456',
    );
    expect(screen.getByText(/An administrator must approve your account/)).toBeDefined();
    expect(
      screen
        .getByRole('link', { name: /Return to sign in/i })
        .getAttribute('href'),
    ).toBe('/login');
  });
});
