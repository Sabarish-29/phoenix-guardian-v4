import { io, Socket } from 'socket.io-client';

type EventHandler = (data: any) => void;

const WS_URL = import.meta.env.VITE_WS_URL || '';

/**
 * WebSocket service for real-time dashboard updates
 */
class SocketService {
  private socket: Socket | null = null;
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;

  /**
   * Connect to WebSocket server
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.socket?.connected) {
        resolve();
        return;
      }

      const token = localStorage.getItem('auth_token');
      
      this.socket = io(WS_URL, {
        path: '/ws/dashboard',
        auth: token ? { token } : undefined,
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: this.maxReconnectAttempts,
        reconnectionDelay: this.reconnectDelay,
        reconnectionDelayMax: 10000,
      });

      this.socket.on('connect', () => {
        console.log('[WebSocket] Connected');
        this.reconnectAttempts = 0;
        resolve();
      });

      this.socket.on('connect_error', (error) => {
        console.error('[WebSocket] Connection error:', error);
        reject(error);
      });

      this.socket.on('disconnect', (reason) => {
        console.log('[WebSocket] Disconnected:', reason);
        this.emit('disconnect', reason);
      });

      this.socket.on('reconnect_attempt', (attempt) => {
        this.reconnectAttempts = attempt;
        this.emit('reconnect_attempt', attempt);
      });

      this.socket.on('reconnect', () => {
        console.log('[WebSocket] Reconnected');
        this.emit('reconnect', null);
      });

      // Set up event forwarding
      this.setupEventForwarding();
    });
  }

  /**
   * Set up forwarding of server events to handlers
   */
  private setupEventForwarding(): void {
    if (!this.socket) return;

    const events = [
      'threat',
      'alert',
      'incident_update',
      'honeytoken_trigger',
      'evidence_ready',
      'model_update',
      'stats_update',
    ];

    events.forEach((event) => {
      this.socket?.on(event, (data) => {
        this.emit(event, data);
      });
    });
  }

  /**
   * Emit event to all registered handlers
   */
  private emit(event: string, data: any): void {
    const handlers = this.handlers.get(event);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data);
        } catch (error) {
          console.error(`[WebSocket] Handler error for ${event}:`, error);
        }
      });
    }
  }

  /**
   * Register event handler
   */
  on(event: string, handler: EventHandler): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set());
    }
    this.handlers.get(event)!.add(handler);
  }

  /**
   * Remove event handler
   */
  off(event: string, handler: EventHandler): void {
    const handlers = this.handlers.get(event);
    if (handlers) {
      handlers.delete(handler);
    }
  }

  /**
   * Send message to server
   */
  send(event: string, data: any): void {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    } else {
      console.warn('[WebSocket] Cannot send - not connected');
    }
  }

  /**
   * Subscribe to a specific room/channel
   */
  subscribe(channel: string): void {
    this.send('subscribe', { channel });
  }

  /**
   * Unsubscribe from a channel
   */
  unsubscribe(channel: string): void {
    this.send('unsubscribe', { channel });
  }

  /**
   * Disconnect from server
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.handlers.clear();
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.socket?.connected ?? false;
  }
}

// Export singleton instance
export const socketService = new SocketService();
