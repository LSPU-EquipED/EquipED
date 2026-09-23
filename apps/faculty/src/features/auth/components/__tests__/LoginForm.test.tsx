// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { LoginForm } from '../LoginForm';
import * as authModule from '@equiped/auth';
import type { AppAuthContext } from '@equiped/auth';

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children, to, className }: { children: React.ReactNode; to: string; className?: string }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

describe('LoginForm Component', () => {
  const mockLogin = vi.fn();
  const mockClearError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    vi.spyOn(authModule, 'useAuth').mockReturnValue({
      status: 'unauthenticated',
      user: null,
      error: null,
      login: mockLogin,
      logout: vi.fn(),
      clearError: mockClearError,
      refresh: vi.fn(),
    } as unknown as AppAuthContext);
  });

  afterEach(() => {
    cleanup();
  });

  it('renders brand hero with institutional identity and no AI grid artifacts', () => {
    render(<LoginForm />);

    expect(screen.getByRole('heading', { name: /Laguna State/i, hidden: true })).toBeDefined();
    expect(screen.getByText('Santa Cruz Campus')).toBeDefined();
    expect(screen.getByRole('heading', { name: 'EquipED Workspace', hidden: true })).toBeDefined();
    expect(screen.getByText(/Faculty Ledger System/i)).toBeDefined();
  });

  it('renders login form inputs, labels, and action button', () => {
    render(<LoginForm />);

    expect(screen.getByLabelText(/^Email/i)).toBeDefined();
    expect(screen.getByLabelText(/^Password/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeDefined();
    expect(screen.getByText(/Remember my email address/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Reset Password/i })).toBeDefined();
  });

  it('toggles password visibility with show/hide button', () => {
    render(<LoginForm />);

    const passwordInput = screen.getByLabelText(/^Password/i) as HTMLInputElement;
    const toggleButton = screen.getByRole('button', { name: /Show password/i });

    expect(passwordInput.type).toBe('password');

    fireEvent.click(toggleButton);
    expect(passwordInput.type).toBe('text');
    expect(screen.getByRole('button', { name: /Hide password/i })).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: /Hide password/i }));
    expect(passwordInput.type).toBe('password');
  });

  it('validates email format on blur when not an @lspu.edu.ph address', () => {
    render(<LoginForm />);

    const emailInput = screen.getByLabelText(/^Email/i);
    fireEvent.change(emailInput, { target: { value: 'user@gmail.com' } });
    fireEvent.blur(emailInput);

    expect(
      screen.getByText('Please use your official @lspu.edu.ph email address.'),
    ).toBeDefined();
  });

  it('keeps email hint empty on blur when email is empty', () => {
    render(<LoginForm />);

    const emailInput = screen.getByLabelText(/^Email/i);
    fireEvent.change(emailInput, { target: { value: '' } });
    fireEvent.blur(emailInput);

    expect(
      screen.queryByText('Please use your official @lspu.edu.ph email address.'),
    ).toBeNull();
    expect(
      screen.queryByText('Email must be 40 characters or fewer.'),
    ).toBeNull();
  });

  it('validates email max length on blur and on submit', async () => {
    render(<LoginForm />);

    const emailInput = screen.getByLabelText(/^Email/i);
    const longEmail = `${'a'.repeat(30)}@lspu.edu.ph`; // 42 chars > 40
    fireEvent.change(emailInput, { target: { value: longEmail } });
    fireEvent.blur(emailInput);

    expect(
      screen.getByText('Email must be 40 characters or fewer.'),
    ).toBeDefined();

    const submitBtn = screen.getByRole('button', { name: /^Sign In$/i });
    fireEvent.click(submitBtn);

    expect(mockLogin).not.toHaveBeenCalled();
    expect(
      screen.getByText('Email must be 40 characters or fewer.'),
    ).toBeDefined();
  });

  it('submits with trimmed lowercase normalized email', async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<LoginForm />);

    const emailInput = screen.getByLabelText(/^Email/i);
    const passwordInput = screen.getByLabelText(/^Password/i);

    fireEvent.change(emailInput, { target: { value: '  Faculty.Member@LSPU.EDU.PH  ' } });
    fireEvent.change(passwordInput, { target: { value: 'validPassword123' } });

    const submitBtn = screen.getByRole('button', { name: /^Sign In$/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'faculty.member@lspu.edu.ph',
        password: 'validPassword123',
      });
    });
  });

  it('toggles remember email checkbox and persists to localStorage on submit', async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<LoginForm />);

    const emailInput = screen.getByLabelText(/^Email/i);
    const passwordInput = screen.getByLabelText(/^Password/i);
    const rememberCheckbox = screen.getByLabelText(/Remember my email address/i) as HTMLInputElement;

    fireEvent.change(emailInput, { target: { value: 'faculty@lspu.edu.ph' } });
    fireEvent.change(passwordInput, { target: { value: 'validPassword123' } });

    expect(rememberCheckbox.checked).toBe(false);
    fireEvent.click(rememberCheckbox);
    expect(rememberCheckbox.checked).toBe(true);

    const submitBtn = screen.getByRole('button', { name: /^Sign In$/i });
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'faculty@lspu.edu.ph',
        password: 'validPassword123',
      });
      expect(localStorage.getItem('remembered_email')).toBe('faculty@lspu.edu.ph');
    });
  });

  it('opens and closes the password reset dialog', () => {
    render(<LoginForm />);

    expect(screen.queryByRole('dialog')).toBeNull();

    const forgotBtn = screen.getByRole('button', { name: /Reset Password/i });
    fireEvent.click(forgotBtn);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeDefined();
    expect(screen.getByText(/Password Reset Protocol/i)).toBeDefined();
    expect(screen.getByText(/Campus Institutional Administrator/i)).toBeDefined();

    const closeBtn = screen.getByRole('button', { name: /Close dialog/i });
    fireEvent.click(closeBtn);

    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('displays authentication error banner when auth.error is set', () => {
    vi.spyOn(authModule, 'useAuth').mockReturnValue({
      status: 'unauthenticated',
      user: null,
      error: 'Invalid credentials. Please verify your email and password.',
      login: mockLogin,
      logout: vi.fn(),
      clearError: mockClearError,
      refresh: vi.fn(),
    } as unknown as AppAuthContext);

    render(<LoginForm />);

    expect(
      screen.getByText('Invalid credentials. Please verify your email and password.'),
    ).toBeDefined();
  });
});
