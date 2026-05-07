import { type Dispatch, type SetStateAction, useCallback, useState } from 'react';

export interface UseToggleReturn {
  value: boolean;
  setValue: Dispatch<SetStateAction<boolean>>;
  setTrue: () => void;
  setFalse: () => void;
  toggle: () => void;
}

export function useToggle(initialValue = false): UseToggleReturn {
  const [value, setValue] = useState(initialValue);

  const setTrue = useCallback(() => setValue(true), []);
  const setFalse = useCallback(() => setValue(false), []);
  const toggle = useCallback(() => setValue((current) => !current), []);

  return {
    value,
    setValue,
    setTrue,
    setFalse,
    toggle,
  };
}
