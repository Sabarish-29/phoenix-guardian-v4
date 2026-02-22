import { useState, useEffect } from 'react';

interface ConnectivityStatus {
  mode: 'online' | 'degraded' | 'demo' | 'offline' | 'checking';
  groqApi: boolean;
  orphadata: boolean;
  openFda: boolean;
}

export const useConnectivity = (): ConnectivityStatus => {
  const [status, setStatus] = useState<ConnectivityStatus>({
    mode: 'checking',
    groqApi: false,
    orphadata: false,
    openFda: false,
  });

  useEffect(() => {
    const check = async () => {
      try {
        const resp = await fetch('/api/v1/system/connectivity');
        if (!resp.ok) throw new Error('Not reachable');
        const data = await resp.json();
        setStatus({
          mode: data.mode,
          groqApi: data.groq_api,
          orphadata: data.orphadata,
          openFda: data.open_fda,
        });
      } catch {
        setStatus(prev => ({ ...prev, mode: 'offline' }));
      }
    };

    check();
    const interval = setInterval(check, 60_000);
    return () => clearInterval(interval);
  }, []);

  return status;
};
