// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { FormEvent } from 'react';
import { useLoginForm } from '../useLoginForm';
import * as authModule from '@equiped/auth';
import type { AppAuthContext } from '@equiped/auth';

describe('useLoginForm', () => {
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

  const createPreventedSubmitEvent = () =>
    ({
      preventDefault: vi.fn(),
    }) as unknown as FormEvent<HTMLFormElement>;

  it('leaves emailHint empty when blurring empty email', () => {
    const { result } = renderHook(() => useLoginForm());

    act(() => {
      result.current.handleEmailBlur();
    });

    expect(result.current.emailHint).toBe('');
  });

  it('rejects direct submit when email is empty and sets official domain hint without calling login', async () => {
    const { result } = renderHook(() => useLoginForm());

    await act(async () => {
      await result.current.handleSubmit(createPreventedSubmitEvent());
    });

    expect(mockLogin).not.toHaveBeenCalled();
    expect(result.current.emailHint).toBe('Please use your official @lspu.edu.ph email address.');
  });

  it('rejects direct submit when email is too long and sets 40-char max hint without calling login', async () => {
    const { result } = renderHook(() => useLoginForm());

    act(() => {
      result.current.setEmail(`${'a'.repeat(30)}@lspu.edu.ph`); // 42 chars
    });

    await act(async () => {
      await result.current.handleSubmit(createPreventedSubmitEvent());
    });

    expect(mockLogin).not.toHaveBeenCalled();
    expect(result.current.emailHint).toBe('Email must be 40 characters or fewer.');
  });

  it('submits normalized email and calls auth.login for valid credentials', async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useLoginForm());

    act(() => {
      result.current.setEmail('  Faculty.User@LSPU.EDU.PH  ');
      result.current.setPassword('validPassword123');
    });

    await act(async () => {
      await result.current.handleSubmit(createPreventedSubmitEvent());
    });

    expect(mockLogin).toHaveBeenCalledWith({
      email: 'faculty.user@lspu.edu.ph',
      password: 'validPassword123',
    });
    expect(result.current.emailHint).toBe('');
  });
});
