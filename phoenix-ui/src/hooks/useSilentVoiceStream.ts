/**
 * useSilentVoiceStream — WebSocket hook for real-time vitals streaming.
 *
 * Connects to the Silent Voice WebSocket endpoint and receives
 * monitoring updates every 10 seconds. Falls back to REST polling
 * if WebSocket fails 3 times.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { MonitorResult } from '../api/services/silentVoiceService';
import { silentVoiceService } from '../api/services/silentVoiceService';

interface UseSilentVoiceStreamReturn {
  data: MonitorResult | null;
  connected: boolean;
  error: string | null;
  mode: 'websocket' | 'polling';
}

export const useSilentVoiceStream = (patientId: string): UseSilentVoiceStreamReturn => {
  const [data, setData] = useState<MonitorResult | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'websocket' | 'polling'>('websocket');
  const wsRef = useRef<WebSocket | null>(null);
  const failCountRef = useRef(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // ── REST polling fallback ────────────────────────────────────────────
  const startPolling = useCallback(() => {
    if (pollingRef.current) return;
    setMode('polling');
    setConnected(true);

    const poll = async () => {
      try {
        const response = await silentVoiceService.monitor(patientId);
        if (mountedRef.current) {
          setData(response.data);
          setError(null);
        }
      } catch (e: any) {
        if (mountedRef.current) {
          setError('Polling error: ' + (e?.message || 'unknown'));
        }
      }
    };

    poll(); // Initial fetch
    pollingRef.current = setInterval(poll, 10000);
  }, [patientId]);

  // ── WebSocket connect ────────────────────────────────────────────────
  const connect = useCallback(() => {
    if (failCountRef.current >= 3) {
      startPolling();
      return;
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname || 'localhost';
    const wsUrl = `${wsProtocol}//${wsHost}:8000/api/v1/silent-voice/stream/${patientId}`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (mountedRef.current) {
          setConnected(true);
          setError(null);
          failCountRef.current = 0;
        }
      };

      ws.onmessage = (e) => {
        if (mountedRef.current) {
          try {
            setData(JSON.parse(e.data));
          } catch {
            // Ignore parse errors
          }
        }
      };

      ws.onerror = () => {
        if (mountedRef.current) {
          failCountRef.current += 1;
          setError(`WebSocket error (attempt ${failCountRef.current}/3)`);
        }
      };

      ws.onclose = () => {
        if (mountedRef.current) {
          setConnected(false);
          if (failCountRef.current >= 3) {
            startPolling();
          } else {
            // Reconnect after 5 seconds
            setTimeout(connect, 5000);
          }
        }
      };

      wsRef.current = ws;
    } catch {
      failCountRef.current += 1;
      if (failCountRef.current >= 3) {
        startPolling();
      }
    }
  }, [patientId, startPolling]);

  useEffect(() => {
    mountedRef.current = true;
    failCountRef.current = 0;
    connect();

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
      wsRef.current = null;
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [connect]);

  return { data, connected, error, mode };
};

export default useSilentVoiceStream;
