import { useEffect, useRef, useState } from 'react';

export function useCredentialCopy(url: string) {
  const [copyState, setCopyState] = useState<'idle' | 'copying' | 'copied' | 'error'>('idle');
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const mountedRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearTimeout(timerRef.current);
    };
  }, []);

  async function copy() {
    clearTimeout(timerRef.current);
    setCopyState('copying');
    try {
      await navigator.clipboard.writeText(url);
      if (!mountedRef.current) return;
      setCopyState('copied');
      timerRef.current = setTimeout(() => setCopyState('idle'), 2000);
    } catch {
      if (mountedRef.current) setCopyState('error');
    }
  }

  return { copyState, copy };
}
