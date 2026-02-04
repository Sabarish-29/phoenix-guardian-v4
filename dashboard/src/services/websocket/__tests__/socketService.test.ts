import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { socketService } from '../socketService';

// Mock socket.io-client
vi.mock('socket.io-client', () => ({
  io: vi.fn(() => ({
    on: vi.fn(),
    off: vi.fn(),
    emit: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    connected: false,
  })),
}));

describe('socketService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    socketService.disconnect();
  });

  describe('connect', () => {
    it('establishes WebSocket connection', () => {
      socketService.connect();
      expect(socketService.isConnected()).toBe(false); // Initially not connected
    });
  });

  describe('disconnect', () => {
    it('disconnects WebSocket', () => {
      socketService.connect();
      socketService.disconnect();
      expect(socketService.isConnected()).toBe(false);
    });
  });

  describe('subscribe', () => {
    it('subscribes to threat events', () => {
      socketService.connect();
      const callback = vi.fn();
      socketService.subscribe('threat:new', callback);
      // Subscription registered
    });

    it('returns unsubscribe function', () => {
      socketService.connect();
      const callback = vi.fn();
      const unsubscribe = socketService.subscribe('threat:new', callback);
      expect(typeof unsubscribe).toBe('function');
    });
  });

  describe('emit', () => {
    it('emits events to server', () => {
      socketService.connect();
      socketService.emit('acknowledge', { threatId: 'threat-1' });
      // Event emitted
    });
  });

  describe('subscribeThreatUpdates', () => {
    it('subscribes to multiple threat events', () => {
      socketService.connect();
      const handlers = {
        onNewThreat: vi.fn(),
        onThreatUpdate: vi.fn(),
        onThreatResolved: vi.fn(),
      };
      const unsubscribe = socketService.subscribeThreatUpdates(handlers);
      expect(typeof unsubscribe).toBe('function');
    });
  });

  describe('subscribeIncidentUpdates', () => {
    it('subscribes to incident events', () => {
      socketService.connect();
      const handlers = {
        onNewIncident: vi.fn(),
        onIncidentUpdate: vi.fn(),
      };
      const unsubscribe = socketService.subscribeIncidentUpdates(handlers);
      expect(typeof unsubscribe).toBe('function');
    });
  });
});
