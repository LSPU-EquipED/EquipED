import { useEffect, type RefObject } from 'react';

export interface UseClickOutsideOptions {
  enabled?: boolean;
}

/**
 * Invokes a callback when a mousedown event occurs outside the referenced element(s).
 */
export function useClickOutside<T extends HTMLElement = HTMLElement>(
  target: RefObject<T | null> | Array<RefObject<HTMLElement | null>>,
  handler: (event: MouseEvent) => void,
  options: UseClickOutsideOptions = {},
): void {
  const { enabled = true } = options;

  useEffect(() => {
    if (!enabled) return;

    function handleMouseDown(event: MouseEvent) {
      const targets = Array.isArray(target) ? target : [target];
      const clickedInside = targets.some((ref) => {
        const el = ref.current;
        return el ? el.contains(event.target as Node) : false;
      });

      if (!clickedInside) {
        handler(event);
      }
    }

    document.addEventListener('mousedown', handleMouseDown);
    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
    };
  }, [target, handler, enabled]);
}
