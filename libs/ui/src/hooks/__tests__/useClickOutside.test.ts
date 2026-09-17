import { describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useClickOutside } from '../useClickOutside';

describe('useClickOutside hook', () => {
  it('triggers handler when clicking outside target element', () => {
    const handler = vi.fn();
    const container = document.createElement('div');
    const outside = document.createElement('button');
    document.body.appendChild(container);
    document.body.appendChild(outside);

    const ref = { current: container };
    renderHook(() => useClickOutside(ref, handler));

    outside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(handler).toHaveBeenCalledTimes(1);

    container.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(handler).toHaveBeenCalledTimes(1);

    document.body.removeChild(container);
    document.body.removeChild(outside);
  });

  it('does not trigger handler when disabled', () => {
    const handler = vi.fn();
    const container = document.createElement('div');
    const outside = document.createElement('button');
    document.body.appendChild(container);
    document.body.appendChild(outside);

    const ref = { current: container };
    renderHook(() => useClickOutside(ref, handler, { enabled: false }));

    outside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    expect(handler).not.toHaveBeenCalled();

    document.body.removeChild(container);
    document.body.removeChild(outside);
  });
});
