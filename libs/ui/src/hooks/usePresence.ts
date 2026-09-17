import { useEffect, useState } from 'react';

export interface UsePresenceOptions {
  isOpen: boolean;
  durationMs?: number;
}

export function usePresence({ isOpen, durationMs = 200 }: UsePresenceOptions) {
  const [isMounted, setIsMounted] = useState(isOpen);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setIsMounted(true);
      const frame = requestAnimationFrame(() => {
        setIsAnimating(true);
      });
      return () => cancelAnimationFrame(frame);
    } else {
      setIsAnimating(false);
      const timer = setTimeout(() => {
        setIsMounted(false);
      }, durationMs);
      return () => clearTimeout(timer);
    }
  }, [isOpen, durationMs]);

  return { isMounted, isAnimating };
}
