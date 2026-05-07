import { useCallback, useEffect, useRef, useState } from 'react';

interface UseFetchOptions<TData> {
  immediate?: boolean;
  initialData?: TData | null;
}

interface UseFetchWithArgsOptions<TData, TArgs extends unknown[]> extends UseFetchOptions<TData> {
  immediateArgs?: TArgs;
}

export function useFetch<TData, TArgs extends unknown[] = []>(
  fetcher: (...args: TArgs) => Promise<TData>,
  options: UseFetchWithArgsOptions<TData, TArgs> = {},
) {
  const { immediate = false, immediateArgs, initialData = null } = options;
  const [data, setData] = useState<TData | null>(initialData);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(
    async (...args: TArgs): Promise<TData> => {
      setIsLoading(true);
      setError(null);
      setIsSuccess(false);

      try {
        const response = await fetcher(...args);

        if (mountedRef.current) {
          setData(response);
          setIsSuccess(true);
        }

        return response;
      } catch (cause) {
        const normalizedError = cause instanceof Error ? cause : new Error('Unexpected fetch error');

        if (mountedRef.current) {
          setError(normalizedError);
        }

        throw normalizedError;
      } finally {
        if (mountedRef.current) {
          setIsLoading(false);
        }
      }
    },
    [fetcher],
  );

  useEffect(() => {
    if (!immediate || !immediateArgs) {
      return;
    }

    let isMounted = true;

    const runFetch = async () => {
      setIsLoading(true);
      setError(null);
      setIsSuccess(false);

      try {
        const response = await fetcher(...immediateArgs);
        if (isMounted) {
          setData(response);
          setIsSuccess(true);
        }
      } catch (cause) {
        const normalizedError = cause instanceof Error ? cause : new Error('Unexpected fetch error');
        if (isMounted) {
          setError(normalizedError);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void runFetch();

    return () => {
      isMounted = false;
    };
  }, [immediate, immediateArgs, fetcher]);

  return {
    data,
    error,
    isLoading,
    isSuccess,
    execute,
    setData,
  };
}

export type { UseFetchOptions, UseFetchWithArgsOptions };
