import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { usePresence } from '../usePresence';

describe('usePresence', () => {
  it('returns isMounted true and isAnimating true when initially open', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePresence({ isOpen: true, durationMs: 200 }));

    expect(result.current.isMounted).toBe(true);

    // After animation frame
    act(() => {
      vi.advanceTimersByTime(16);
    });

    expect(result.current.isMounted).toBe(true);
    expect(result.current.isAnimating).toBe(true);
    vi.useRealTimers();
  });

  it('keeps isMounted true during closing animation and unmounts after durationMs', async () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ isOpen }) => usePresence({ isOpen, durationMs: 200 }),
      { initialProps: { isOpen: true } },
    );

    act(() => {
      vi.advanceTimersByTime(16);
    });
    expect(result.current.isAnimating).toBe(true);

    // Trigger close
    rerender({ isOpen: false });

    // Instantly animating false, but still mounted
    expect(result.current.isAnimating).toBe(false);
    expect(result.current.isMounted).toBe(true);

    // Advance halfway through duration
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(result.current.isMounted).toBe(true);

    // Advance past durationMs
    act(() => {
      vi.advanceTimersByTime(110);
    });
    expect(result.current.isMounted).toBe(false);

    vi.useRealTimers();
  });
});
