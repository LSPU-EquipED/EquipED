import { useCallback, useState } from 'react';

type SetValue<T> = (value: T | ((current: T) => T)) => void;

function readStoredValue<T>(key: string, initialValue: T): T {
  if (typeof window === 'undefined') {
    return initialValue;
  }

  const item = window.localStorage.getItem(key);
  if (!item) {
    return initialValue;
  }

  try {
    return JSON.parse(item) as T;
  } catch {
    return initialValue;
  }
}

export function useLocalStorage<T>(key: string, initialValue: T): [T, SetValue<T>] {
  const [storedValue, setStoredValue] = useState<T>(() => readStoredValue(key, initialValue));

  const setValue: SetValue<T> = useCallback(
    (value) => {
      setStoredValue((current) => {
        const valueToStore = value instanceof Function ? value(current) : value;
        window.localStorage.setItem(key, JSON.stringify(valueToStore));
        return valueToStore;
      });
    },
    [key],
  );

  return [storedValue, setValue];
}
