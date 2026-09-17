// @vitest-environment jsdom
import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { useClipboardCopy } from '../useClipboardCopy';

describe('useClipboardCopy', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('initializes with copied = false', () => {
    const { result } = renderHook(() => useClipboardCopy());
    expect(result.current.copied).toBe(false);
  });

  it('sets copied = true upon copy and resets after default 2000ms', async () => {
    const { result } = renderHook(() => useClipboardCopy());

    await act(async () => {
      const success = await result.current.copy('test-text');
      expect(success).toBe(true);
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('test-text');
    expect(result.current.copied).toBe(true);

    act(() => {
      vi.advanceTimersByTime(1999);
    });
    expect(result.current.copied).toBe(true);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current.copied).toBe(false);
  });

  it('resets timer on repeat copy before initial timeout finishes', async () => {
    const { result } = renderHook(() => useClipboardCopy({ resetTimeoutMs: 2000 }));

    await act(async () => {
      await result.current.copy('text-1');
    });
    expect(result.current.copied).toBe(true);

    // Advance 1500ms (500ms remaining before reset)
    act(() => {
      vi.advanceTimersByTime(1500);
    });
    expect(result.current.copied).toBe(true);

    // Repeated copy should restart the 2000ms window
    await act(async () => {
      await result.current.copy('text-2');
    });
    expect(result.current.copied).toBe(true);

    // Advance 1000ms (original would have expired at 2000ms, but new one has 1000ms left)
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.copied).toBe(true);

    // Advance the remaining 1000ms
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.copied).toBe(false);
  });

  it('cleans up active timer on unmount without throwing or triggering state update', async () => {
    const clearTimeoutSpy = vi.spyOn(window, 'clearTimeout');
    const { result, unmount } = renderHook(() => useClipboardCopy());

    await act(async () => {
      await result.current.copy('cleanup-test');
    });
    expect(result.current.copied).toBe(true);

    unmount();
    expect(clearTimeoutSpy).toHaveBeenCalled();

    // Advance timer past window to ensure no warnings or post-unmount updates occur
    act(() => {
      vi.advanceTimersByTime(3000);
    });
  });

  it('returns false and does not copy empty text', async () => {
    const { result } = renderHook(() => useClipboardCopy());

    await act(async () => {
      const res = await result.current.copy('');
      expect(res).toBe(false);
    });

    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
    expect(result.current.copied).toBe(false);
  });

  it('handles clipboard API rejection gracefully', async () => {
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error('Permission denied'));
    const { result } = renderHook(() => useClipboardCopy());

    await act(async () => {
      const res = await result.current.copy('fail');
      expect(res).toBe(false);
    });

    expect(result.current.copied).toBe(false);
  });

  it('drops async completion after unmount and does not update state', async () => {
    let resolveWriteText: () => void = () => {};
    vi.mocked(navigator.clipboard.writeText).mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveWriteText = resolve;
        }),
    );

    const { result, unmount } = renderHook(() => useClipboardCopy());

    let copyPromise: Promise<boolean>;
    act(() => {
      copyPromise = result.current.copy('unmount-pending-test');
    });

    expect(result.current.copied).toBe(false);
    expect(result.current.copiedValue).toBeNull();

    unmount();

    await act(async () => {
      resolveWriteText();
      const outcome = await copyPromise;
      expect(outcome).toBe(false);
    });

    expect(result.current.copied).toBe(false);
    expect(result.current.copiedValue).toBeNull();
  });

  it('handles overlapping copy calls and only allows the latest operation to update state', async () => {
    let resolveFirst: () => void = () => {};
    let resolveSecond: () => void = () => {};

    vi.mocked(navigator.clipboard.writeText)
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveSecond = resolve;
          }),
      );

    const { result } = renderHook(() => useClipboardCopy({ resetTimeoutMs: 1000 }));

    let firstPromise: Promise<boolean>;
    let secondPromise: Promise<boolean>;

    act(() => {
      firstPromise = result.current.copy('first-value');
      secondPromise = result.current.copy('second-value');
    });

    // Resolve first (stale operation)
    await act(async () => {
      resolveFirst();
      const firstOutcome = await firstPromise;
      expect(firstOutcome).toBe(false);
    });

    // Stale completion should not have set copiedValue
    expect(result.current.copiedValue).toBeNull();
    expect(result.current.copied).toBe(false);

    // Resolve second (latest operation)
    await act(async () => {
      resolveSecond();
      const secondOutcome = await secondPromise;
      expect(secondOutcome).toBe(true);
    });

    expect(result.current.copiedValue).toBe('second-value');
    expect(result.current.copied).toBe(true);

    // After reset timeout, second-value resets
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.copiedValue).toBeNull();
    expect(result.current.copied).toBe(false);
  });
});
