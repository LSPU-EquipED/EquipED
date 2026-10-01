import { useEffect, useState } from 'react';

// One clock drives both URL expiry displays for the lifetime of the handoff.
export function useCredentialClock(): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  return now;
}
