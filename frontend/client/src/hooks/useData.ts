import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../utils/api';
interface UseDataResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

function useFetch<T>(fetchFn: () => Promise<T>, deps: unknown[] = []): UseDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchFnRef = useRef(fetchFn);
  useEffect(() => {
    fetchFnRef.current = fetchFn;
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFnRef.current();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let isCancelled = false;

    const execute = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchFnRef.current();
        if (!isCancelled) {
          setData(result);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof Error ? err : new Error('Unknown error'));
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    execute();

    return () => {
      isCancelled = true;
    };
  }, deps);

  return { data, loading, error, refetch: fetchData };
}

export function useStructureCheckpoints() {
  return useFetch(() => api.structure.all());
}

export function useLatestStructureCheckpoint() {
  return useFetch(() => api.structure.latest());
}

export function useStructureComparison() {
  return useFetch(() => api.structure.comparison());
}

export function useStructureGraph(model: 'bdh' | 'transformer') {
  return useFetch(() => api.structure.graph(model), [model]);
}

export function useContinualLearning() {
  return useFetch(() => api.continual.all());
}

export function useReasoning() {
  return useFetch(() => api.reasoning.all());
}

export function useReasoningComparison() {
  return useFetch(() => api.reasoning.comparison());
}

export function useModelConfig() {
  return useFetch(() => api.config.model());
}

