// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useDashboardGreeting } from '../useDashboardGreeting';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('useDashboardGreeting', () => {
  it('refreshes the local greeting and date across midnight, and clears the timer on unmount', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 1, 23, 59));
    const { result, unmount } = renderHook(() => useDashboardGreeting(' Jeremy Garin '));
    expect(result.current.greeting).toBe('Good evening, Jeremy.');
    expect(result.current.dateTime).toBe('2026-10-01');

    act(() => vi.advanceTimersByTime(60_000));
    expect(result.current.greeting).toBe('Welcome back, Jeremy.');
    expect(result.current.dateTime).toBe('2026-10-02');
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('refreshes when the tab becomes visible and removes its listener on unmount', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 1, 8));
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
    const removeListener = vi.spyOn(document, 'removeEventListener');
    const { result, unmount } = renderHook(() => useDashboardGreeting());

    vi.setSystemTime(new Date(2026, 9, 1, 18));
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    expect(result.current.greeting).toBe('Good evening.');
    unmount();
    expect(removeListener).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  });
});
