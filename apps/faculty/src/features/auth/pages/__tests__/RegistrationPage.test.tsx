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

function fillRegistration(program = 'BSCS') {
  const values = [
    [/Full name/i, 'Prof. Maria Santos'],
    [/LSPU email/i, 'msantos@lspu.edu.ph'],
    [/Faculty ID/i, '2024-FAC-019'],
    [/Department/i, 'College of Computer Studies'],
    [/^Password$/i, 'securePass123'],
  ] as const;
  for (const [label, value] of values) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  if (program) {
    fireEvent.click(screen.getByLabelText(/^Program$/i));
    fireEvent.click(screen.getByRole('option', { name: program }));
  }
}

describe('RegistrationPage Component', () => {
  beforeEach(() => {
    vi.resetAllMocks();
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

    fillRegistration();

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
    expect(
      screen.getByText(/An administrator must approve your account/),
    ).toBeDefined();
    expect(
      screen
        .getByRole('link', { name: /Return to sign in/i })
        .getAttribute('href'),
    ).toBe('/login');
  });

  it('requires a program selection and sends the canonical dropdown value', async () => {
    vi.mocked(registrationApi.start).mockResolvedValueOnce({
      registration_token: 'token-program',
      email: 'msantos@lspu.edu.ph',
      message: 'Sent',
    });
    render(<RegistrationPage />);
    fillRegistration('');
    fireEvent.click(
      screen.getByRole('button', { name: /Send verification code/i }),
    );
    expect(registrationApi.start).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toBe('Select your program.');
    const program = screen.getByLabelText(/^Program$/i);
    expect(program.getAttribute('aria-invalid')).toBe('true');
    expect(document.activeElement).toBe(program);
    fireEvent.keyDown(program, { key: 'Enter' });
    const listbox = screen.getByRole('listbox');
    fireEvent.keyDown(listbox, { key: 'End' });
    fireEvent.keyDown(listbox, { key: 'Enter' });
    expect(screen.queryByRole('alert')).toBeNull();
    fireEvent.click(
      screen.getByRole('button', { name: /Send verification code/i }),
    );
    await waitFor(() =>
      expect(registrationApi.start).toHaveBeenCalledWith(
        expect.objectContaining({ program: 'BSInfoTech' }),
      ),
    );
  });

  it('announces sending, prevents duplicate submission, and allows retry after failure', async () => {
    let failRequest!: (error: Error) => void;
    vi.mocked(registrationApi.start).mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          failRequest = reject;
        }),
    );
    render(<RegistrationPage />);
    fillRegistration();
    fireEvent.click(
      screen.getByRole('button', { name: /Send verification code/i }),
    );
    const sending = screen.getByRole('button', {
      name: 'Sending code…',
    }) as HTMLButtonElement;
    expect(sending.disabled).toBe(true);
    expect(sending.getAttribute('aria-busy')).toBe('true');
    expect(sending.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    expect(screen.getByRole('status').textContent).toBe('Sending code…');
    fireEvent.click(sending);
    expect(registrationApi.start).toHaveBeenCalledTimes(1);
    await act(async () => failRequest(new Error('Unable to send code')));
    expect(screen.getByRole('alert').textContent).toContain(
      'Unable to send code',
    );
    expect(
      (
        screen.getByRole('button', {
          name: /Send verification code/i,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
    expect(screen.getByRole('status').textContent).toBe('');
  });

  it('distinguishes resend and verification loading while preserving pending approval', async () => {
    vi.mocked(registrationApi.start).mockResolvedValueOnce({
      registration_token: 'token-loading',
      email: 'msantos@lspu.edu.ph',
      message: 'Sent',
    });
    let finishResend!: (
      result: Awaited<ReturnType<typeof registrationApi.resend>>,
    ) => void;
    vi.mocked(registrationApi.resend).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishResend = resolve;
        }),
    );
    let finishVerify!: (
      result: Awaited<ReturnType<typeof registrationApi.verify>>,
    ) => void;
    vi.mocked(registrationApi.verify).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishVerify = resolve;
        }),
    );
    render(<RegistrationPage />);
    fillRegistration();
    fireEvent.click(
      screen.getByRole('button', { name: /Send verification code/i }),
    );
    await screen.findByRole('heading', { name: /Verify your email/i });
    fireEvent.click(screen.getByRole('button', { name: /Resend code/i }));
    const resending = screen.getByRole('button', {
      name: 'Resending code…',
    }) as HTMLButtonElement;
    expect(resending.disabled).toBe(true);
    expect(resending.getAttribute('aria-busy')).toBe('true');
    expect(screen.getByRole('status').textContent).toBe('Resending code…');
    expect(
      (
        screen.getByRole('button', {
          name: /Verify email/i,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    await act(async () =>
      finishResend({
        registration_token: 'token-loading',
        email: 'msantos@lspu.edu.ph',
        message: 'Sent',
      }),
    );
    fireEvent.change(screen.getByLabelText(/Verification code/i), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify email/i }));
    const verifying = screen.getByRole('button', {
      name: 'Verifying email…',
    }) as HTMLButtonElement;
    expect(verifying.disabled).toBe(true);
    expect(verifying.getAttribute('aria-busy')).toBe('true');
    expect(screen.getByRole('status').textContent).toBe('Verifying email…');
    expect(
      (
        screen.getByRole('button', {
          name: /Resend code/i,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    await act(async () =>
      finishVerify({ status: 'pending_approval', message: 'Verified' }),
    );
    expect(
      screen.getByText(/An administrator must approve your account/),
    ).toBeDefined();
  });
});
