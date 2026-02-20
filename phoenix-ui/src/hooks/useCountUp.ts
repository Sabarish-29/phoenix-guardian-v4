/**
 * useCountUp — animated counter hook.
 * Counts from 0 to a target number over a duration.
 * Used for years_lost, distress_duration, pct_change, etc.
 */

import { useState, useEffect } from 'react';

export const useCountUp = (target: number, duration: number = 1500, decimals: number = 0): number => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (target === 0) {
      setCount(0);
      return;
    }

    const steps = 30;
    const increment = target / steps;
    const interval = duration / steps;
    let current = 0;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      current += increment;
      if (step >= steps || current >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        const factor = Math.pow(10, decimals);
        setCount(Math.round(current * factor) / factor);
      }
    }, interval);

    return () => clearInterval(timer);
  }, [target, duration, decimals]);

  return count;
};

export default useCountUp;
