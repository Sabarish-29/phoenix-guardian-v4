import { useEffect, useRef, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from './useStore';
import { selectRefreshInterval } from '../store/slices/settingsSlice';

/**
 * Hook for auto-refreshing data at configured intervals
 */
export function useAutoRefresh(
  fetchAction: () => any,
  enabled: boolean = true,
  overrideInterval?: number
) {
  const dispatch = useAppDispatch();
  const configuredInterval = useAppSelector(selectRefreshInterval);
  const interval = overrideInterval ?? configuredInterval;
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const refresh = useCallback(() => {
    dispatch(fetchAction());
  }, [dispatch, fetchAction]);

  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Initial fetch
    refresh();

    // Set up interval
    intervalRef.current = setInterval(refresh, interval * 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [refresh, enabled, interval]);

  return { refresh };
}
