// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useHistoryDrawer } from '../useHistoryDrawer';

describe('useHistoryDrawer', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('initializes with drawer closed and not closing', () => {
    const { result } = renderHook(() => useHistoryDrawer());
    expect(result.current.showHistorySidebar).toBe(false);
    expect(result.current.isHistorySidebarClosing).toBe(false);
  });

  it('opens and closes with 240ms exit animation timer', () => {
    const { result } = renderHook(() => useHistoryDrawer());

    act(() => {
      result.current.openHistorySidebar();
    });
    expect(result.current.showHistorySidebar).toBe(true);
    expect(result.current.isHistorySidebarClosing).toBe(false);

    act(() => {
      result.current.closeHistorySidebar();
    });
    expect(result.current.showHistorySidebar).toBe(true);
    expect(result.current.isHistorySidebarClosing).toBe(true);

    act(() => {
      vi.advanceTimersByTime(240);
    });
    expect(result.current.showHistorySidebar).toBe(false);
    expect(result.current.isHistorySidebarClosing).toBe(false);
  });
});
