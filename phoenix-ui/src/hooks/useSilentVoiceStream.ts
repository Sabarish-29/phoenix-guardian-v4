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

export const useSilentVoiceStream = (patientId: string, language: string = 'en'): UseSilentVoiceStreamReturn => {
  const [data, setData] = useState<MonitorResult | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'websocket' | 'polling'>('polling');
  const wsRef = useRef<WebSocket | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  const wsUpgraded = useRef(false);

  // ── REST polling (starts immediately for fast first paint) ───────────
  const poll = useCallback(async () => {
    try {
      const response = await silentVoiceService.monitor(patientId, language);
      if (mountedRef.current) {
        setData(response.data);
        setConnected(true);
        setError(null);
      }
    } catch (e: any) {
      if (mountedRef.current) {
        setError('Polling error: ' + (e?.message || 'unknown'));
      }
    }
  }, [patientId, language]);

  const startPolling = useCallback(() => {
    if (pollingRef.current) return;
    pollingRef.current = setInterval(poll, 10000);
  }, [poll]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  // ── WebSocket upgrade (optional — tried once after initial data loads) ─
  const tryWebSocket = useCallback(() => {
    if (wsUpgraded.current) return;
    wsUpgraded.current = true;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/silent-voice/stream/${patientId}`;

    try {
      const ws = new WebSocket(wsUrl);
      const timeout = setTimeout(() => {
        // If WS hasn't opened in 3 seconds, abandon it
        if (ws.readyState !== WebSocket.OPEN) {
          ws.close();
        }
      }, 3000);

      ws.onopen = () => {
        clearTimeout(timeout);
        if (mountedRef.current) {
          setMode('websocket');
          setConnected(true);
          setError(null);
          stopPolling(); // WS is live, stop REST polling
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
        clearTimeout(timeout);
        // WS failed — keep polling, no retry
      };

      ws.onclose = () => {
        clearTimeout(timeout);
        if (mountedRef.current) {
          // Fell back from WS — restart polling
          setMode('polling');
          startPolling();
        }
      };

      wsRef.current = ws;
    } catch {
      // WS not available — keep polling
    }
  }, [patientId, startPolling, stopPolling]);

  useEffect(() => {
    mountedRef.current = true;
    wsUpgraded.current = false;

    // Immediately fetch data via REST (fast first paint)
    poll().then(() => {
      if (mountedRef.current) {
        startPolling();
        // After first data arrives, try upgrading to WebSocket
        tryWebSocket();
      }
    });

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
      wsRef.current = null;
      stopPolling();
    };
  }, [poll, startPolling, stopPolling, tryWebSocket]);

  return { data, connected, error, mode };
};

export default useSilentVoiceStream;
