// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { LoginForm } from '../LoginForm';
import * as authModule from '@equiped/auth';
import type { AppAuthContext } from '@equiped/auth';

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
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

  it('renders institutional identity and the SLM review purpose', () => {
    render(<LoginForm />);

    expect(
      screen.getByRole('complementary', { name: 'About EquipED' }),
    ).toBeDefined();
    expect(
      screen.getByRole('heading', { name: /Laguna State Polytechnic University/ }),
    ).toBeDefined();
    expect(screen.getByRole('heading', { name: 'EquipED Workspace' })).toBeDefined();
    expect(
      screen.getByText(/Review self-paced learning modules/),
    ).toBeDefined();
    expect(
      screen.getByRole('heading', { name: /Sign in/i, level: 1 }),
    ).toBeDefined();
  });

  it('renders login form inputs, labels, and action button', () => {
    render(<LoginForm />);

    expect(screen.getByLabelText(/^Email/i)).toBeDefined();
    expect(screen.getByLabelText(/^Password/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeDefined();
    expect(screen.getByText(/Remember my email/i)).toBeDefined();
    expect(
      screen.getByRole('button', { name: /Reset Password/i }),
    ).toBeDefined();
  });

  it('toggles password visibility with show/hide button', () => {
    render(<LoginForm />);

    const passwordInput = screen.getByLabelText(
      /^Password/i,
    ) as HTMLInputElement;
    const toggleButton = screen.getByRole('button', { name: /Show password/i });

    expect(passwordInput.type).toBe('password');

    fireEvent.click(toggleButton);
    expect(passwordInput.type).toBe('text');
    expect(
      screen.getByRole('button', { name: /Hide password/i }),
    ).toBeDefined();

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
      screen.queryByText(
        'Please use your official @lspu.edu.ph email address.',
      ),
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

    fireEvent.change(emailInput, {
      target: { value: '  Faculty.Member@LSPU.EDU.PH  ' },
    });
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
    const rememberCheckbox = screen.getByLabelText(
      /Remember my email/i,
    ) as HTMLInputElement;

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
      expect(localStorage.getItem('remembered_email')).toBe(
        'faculty@lspu.edu.ph',
      );
    });
  });

  it('opens and closes the password reset dialog', () => {
    render(<LoginForm />);

    expect(screen.queryByRole('dialog')).toBeNull();

    const forgotBtn = screen.getByRole('button', { name: /Reset Password/i });
    fireEvent.click(forgotBtn);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeDefined();
    expect(
      screen.getByRole('dialog', { name: /Reset password/i }),
    ).toBeDefined();
    expect(
      screen.getByText(/Campus Institutional Administrator/i),
    ).toBeDefined();

    const closeBtn = screen.getByRole('button', { name: /Close dialog/i });
    fireEvent.click(closeBtn);

    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('associates password feedback with the input', () => {
    render(<LoginForm />);
    const password = screen.getByLabelText(/^Password/i);
    fireEvent.change(password, { target: { value: 'short' } });
    fireEvent.blur(password);
    expect(password.getAttribute('aria-invalid')).toBe('true');
    expect(
      document.getElementById(password.getAttribute('aria-describedby')!)
        ?.textContent,
    ).toBe('Minimum 8 characters required.');
  });

  it('disables sign-in while a request is pending and enables it afterward', async () => {
    let finishLogin!: () => void;
    mockLogin.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finishLogin = resolve;
        }),
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/^Email/i), {
      target: { value: 'faculty@lspu.edu.ph' },
    });
    fireEvent.change(screen.getByLabelText(/^Password/i), {
      target: { value: 'validPassword123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Sign in$/i }));
    const button = screen.getByRole('button', {
      name: 'Signing in…',
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(screen.getByRole('status').textContent).toBe('Signing in…');
    expect(button.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    fireEvent.click(button);
    expect(mockLogin).toHaveBeenCalledTimes(1);
    await act(async () => finishLogin());
    expect(
      (screen.getByRole('button', { name: /^Sign in$/i }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it('clears the loading state after a failed sign-in so the user can retry', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/^Email/i), { target: { value: 'faculty@lspu.edu.ph' } });
    fireEvent.change(screen.getByLabelText(/^Password/i), { target: { value: 'validPassword123' } });
    fireEvent.click(screen.getByRole('button', { name: /^Sign in$/i }));
    await waitFor(() => expect((screen.getByRole('button', { name: /^Sign in$/i }) as HTMLButtonElement).disabled).toBe(false));
    expect(screen.getByRole('status').textContent).toBe('');
  });

  it('keeps a loading state until authenticated navigation completes', () => {
    vi.mocked(authModule.useAuth).mockReturnValue({
      status: 'authenticated',
      source: 'server',
      ready: true,
      user: { id: 'faculty-1', email: 'faculty@lspu.edu.ph', displayName: 'Faculty', role: 'faculty' },
      error: null,
      login: mockLogin,
      logout: vi.fn(),
      clearError: mockClearError,
      refresh: vi.fn(),
    });
    render(<LoginForm />);
    const button = screen.getByRole('button', { name: 'Opening your workspace…' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(screen.getByRole('status').textContent).toBe('Opening your workspace…');
  });

  it('traps recovery dialog focus and returns to its trigger on Escape', async () => {
    render(<LoginForm />);
    const trigger = screen.getByRole('button', { name: /Reset password/i });
    trigger.focus();
    fireEvent.click(trigger);
    const close = screen.getByRole('button', { name: 'Close dialog' });
    const done = screen.getByRole('button', { name: 'Got it' });
    await waitFor(() => expect(document.activeElement).toBe(close));
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(done);
    fireEvent.keyDown(done, { key: 'Tab' });
    expect(document.activeElement).toBe(close);
    expect(document.body.style.overflow).toBe('hidden');
    fireEvent.keyDown(close, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(document.body.style.overflow).not.toBe('hidden');
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
      screen.getByText(
        'Invalid credentials. Please verify your email and password.',
      ),
    ).toBeDefined();
  });
});
