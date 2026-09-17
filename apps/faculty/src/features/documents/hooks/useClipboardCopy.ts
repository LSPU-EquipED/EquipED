import { useCallback, useEffect, useRef, useState } from 'react';

interface UseClipboardCopyOptions {
  resetTimeoutMs?: number;
}

export function useClipboardCopy(options: UseClipboardCopyOptions = {}) {
  const { resetTimeoutMs = 2000 } = options;
  const [copiedValue, setCopiedValue] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const operationGenerationRef = useRef(0);

  const clearTimer = useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      if (!text) return false;
      const currentGen = ++operationGenerationRef.current;

      try {
        await navigator.clipboard.writeText(text);

        if (!isMountedRef.current || currentGen !== operationGenerationRef.current) {
          return false;
        }

        clearTimer();
        setCopiedValue(text);

        timeoutRef.current = setTimeout(() => {
          if (!isMountedRef.current || currentGen !== operationGenerationRef.current) {
            return;
          }
          setCopiedValue(null);
          timeoutRef.current = null;
        }, resetTimeoutMs);

        return true;
      } catch {
        // Gracefully handle environments where clipboard API is restricted
        return false;
      }
    },
    [clearTimer, resetTimeoutMs],
  );

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      operationGenerationRef.current += 1;
      clearTimer();
    };
  }, [clearTimer]);

  return {
    copied: copiedValue !== null,
    copiedValue,
    copy,
  };
}

