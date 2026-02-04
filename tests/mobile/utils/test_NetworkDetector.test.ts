/**
 * Phoenix Guardian Mobile - NetworkDetector Tests
 * 
 * Unit tests for the NetworkDetector utility.
 * Tests network status detection, change callbacks, and connectivity verification.
 */

import NetInfo from '@react-native-community/netinfo';
import NetworkDetector, { NetworkDetector as NetworkDetectorClass } from '../../../mobile/src/utils/networkDetector';

// =============================================================================
// MOCKS
// =============================================================================

jest.mock('@react-native-community/netinfo', () => ({
  fetch: jest.fn(),
  addEventListener: jest.fn(),
}));

global.fetch = jest.fn();

// =============================================================================
// TEST UTILITIES
// =============================================================================

const mockNetInfoState = (overrides = {}) => ({
  isConnected: true,
  isInternetReachable: true,
  type: 'wifi',
  details: {
    isConnectionExpensive: false,
    ssid: 'TestNetwork',
  },
  ...overrides,
});

// =============================================================================
// TESTS
// =============================================================================

describe('NetworkDetector', () => {
  let networkChangeCallback: ((state: any) => void) | null = null;

  beforeEach(() => {
    jest.clearAllMocks();
    networkChangeCallback = null;
    
    (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState());
    (NetInfo.addEventListener as jest.Mock).mockImplementation((callback) => {
      networkChangeCallback = callback;
      return jest.fn(); // unsubscribe function
    });
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true });
    
    // Cleanup singleton state
    NetworkDetector.cleanup();
  });

  // ---------------------------------------------------------------------------
  // Initialization Tests
  // ---------------------------------------------------------------------------

  describe('Initialization', () => {
    test('initializes network monitoring successfully', async () => {
      await NetworkDetector.initialize();
      
      expect(NetInfo.fetch).toHaveBeenCalled();
      expect(NetInfo.addEventListener).toHaveBeenCalled();
    });

    test('fetches initial network state on initialization', async () => {
      const mockState = mockNetInfoState({ type: 'cellular' });
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockState);
      
      await NetworkDetector.initialize();
      
      const status = NetworkDetector.getStatus();
      expect(status.type).toBe('cellular');
    });

    test('handles initialization failure gracefully', async () => {
      (NetInfo.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));
      
      // Should not throw
      await expect(NetworkDetector.initialize()).resolves.not.toThrow();
      
      // Should default to online
      const isOnline = await NetworkDetector.isOnline();
      expect(isOnline).toBe(true);
    });

    test('only initializes once', async () => {
      await NetworkDetector.initialize();
      await NetworkDetector.initialize();
      await NetworkDetector.initialize();
      
      expect(NetInfo.fetch).toHaveBeenCalledTimes(1);
    });
  });

  // ---------------------------------------------------------------------------
  // Network Status Tests
  // ---------------------------------------------------------------------------

  describe('Network Status', () => {
    test('reports online when connected with internet', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        isConnected: true,
        isInternetReachable: true,
      }));
      
      const isOnline = await NetworkDetector.isOnline();
      expect(isOnline).toBe(true);
    });

    test('reports offline when disconnected', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        isConnected: false,
        isInternetReachable: false,
      }));
      
      await NetworkDetector.initialize();
      
      const isOnline = await NetworkDetector.isOnline();
      expect(isOnline).toBe(false);
    });

    test('isOnlineSync returns cached status', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        isConnected: true,
      }));
      
      await NetworkDetector.initialize();
      
      expect(NetworkDetector.isOnlineSync()).toBe(true);
    });

    test('getStatus returns complete network information', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        type: 'wifi',
        isConnected: true,
        isInternetReachable: true,
      }));
      
      await NetworkDetector.initialize();
      
      const status = NetworkDetector.getStatus();
      expect(status).toEqual(expect.objectContaining({
        isOnline: true,
        isInternetReachable: true,
        type: 'wifi',
        isWifi: true,
        isCellular: false,
      }));
    });
  });

  // ---------------------------------------------------------------------------
  // Connection Type Tests
  // ---------------------------------------------------------------------------

  describe('Connection Type', () => {
    test('detects WiFi connection', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        type: 'wifi',
      }));
      
      await NetworkDetector.initialize();
      
      expect(NetworkDetector.isOnWifi()).toBe(true);
      expect(NetworkDetector.isOnCellular()).toBe(false);
      expect(NetworkDetector.getConnectionType()).toBe('wifi');
    });

    test('detects cellular connection', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        type: 'cellular',
      }));
      
      await NetworkDetector.initialize();
      
      expect(NetworkDetector.isOnCellular()).toBe(true);
      expect(NetworkDetector.isOnWifi()).toBe(false);
      expect(NetworkDetector.getConnectionType()).toBe('cellular');
    });

    test('handles unknown connection type', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        type: 'unknown',
      }));
      
      await NetworkDetector.initialize();
      
      expect(NetworkDetector.getConnectionType()).toBe('unknown');
      expect(NetworkDetector.isOnWifi()).toBe(false);
      expect(NetworkDetector.isOnCellular()).toBe(false);
    });
  });

  // ---------------------------------------------------------------------------
  // Change Subscription Tests
  // ---------------------------------------------------------------------------

  describe('Change Subscriptions', () => {
    test('calls subscriber when network status changes', async () => {
      await NetworkDetector.initialize();
      
      const callback = jest.fn();
      NetworkDetector.onChange(callback);
      
      // Simulate network going offline
      networkChangeCallback!(mockNetInfoState({ isConnected: false }));
      
      expect(callback).toHaveBeenCalledWith(false);
    });

    test('calls subscriber when network comes back online', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        isConnected: false,
      }));
      
      await NetworkDetector.initialize();
      
      const callback = jest.fn();
      NetworkDetector.onChange(callback);
      
      // Simulate network coming online
      networkChangeCallback!(mockNetInfoState({ isConnected: true }));
      
      expect(callback).toHaveBeenCalledWith(true);
    });

    test('does not call subscriber when status unchanged', async () => {
      await NetworkDetector.initialize();
      
      const callback = jest.fn();
      NetworkDetector.onChange(callback);
      
      // Simulate same status
      networkChangeCallback!(mockNetInfoState({ isConnected: true }));
      
      expect(callback).not.toHaveBeenCalled();
    });

    test('unsubscribe function removes callback', async () => {
      await NetworkDetector.initialize();
      
      const callback = jest.fn();
      const unsubscribe = NetworkDetector.onChange(callback);
      
      // Unsubscribe
      unsubscribe();
      
      // Simulate network change
      networkChangeCallback!(mockNetInfoState({ isConnected: false }));
      
      expect(callback).not.toHaveBeenCalled();
    });

    test('supports multiple subscribers', async () => {
      await NetworkDetector.initialize();
      
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      const callback3 = jest.fn();
      
      NetworkDetector.onChange(callback1);
      NetworkDetector.onChange(callback2);
      NetworkDetector.onChange(callback3);
      
      // Simulate network change
      networkChangeCallback!(mockNetInfoState({ isConnected: false }));
      
      expect(callback1).toHaveBeenCalledWith(false);
      expect(callback2).toHaveBeenCalledWith(false);
      expect(callback3).toHaveBeenCalledWith(false);
    });

    test('handles subscriber errors gracefully', async () => {
      await NetworkDetector.initialize();
      
      const errorCallback = jest.fn().mockImplementation(() => {
        throw new Error('Subscriber error');
      });
      const normalCallback = jest.fn();
      
      NetworkDetector.onChange(errorCallback);
      NetworkDetector.onChange(normalCallback);
      
      // Should not throw
      expect(() => {
        networkChangeCallback!(mockNetInfoState({ isConnected: false }));
      }).not.toThrow();
      
      // Normal callback should still be called
      expect(normalCallback).toHaveBeenCalled();
    });
  });

  // ---------------------------------------------------------------------------
  // Connectivity Verification Tests
  // ---------------------------------------------------------------------------

  describe('Connectivity Verification', () => {
    test('verifies connectivity with ping request', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });
      
      await NetworkDetector.initialize();
      
      const isConnected = await NetworkDetector.verifyConnectivity();
      expect(isConnected).toBe(true);
      expect(global.fetch).toHaveBeenCalled();
    });

    test('returns false when ping fails', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));
      
      await NetworkDetector.initialize();
      
      const isConnected = await NetworkDetector.verifyConnectivity();
      expect(isConnected).toBe(false);
    });

    test('returns false when not connected', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        isConnected: false,
      }));
      
      await NetworkDetector.initialize();
      
      const isConnected = await NetworkDetector.verifyConnectivity();
      expect(isConnected).toBe(false);
      expect(global.fetch).not.toHaveBeenCalled();
    });

    test('returns false when ping returns non-ok status', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: false, status: 500 });
      
      await NetworkDetector.initialize();
      
      const isConnected = await NetworkDetector.verifyConnectivity();
      expect(isConnected).toBe(false);
    });
  });

  // ---------------------------------------------------------------------------
  // Wait For Connection Tests
  // ---------------------------------------------------------------------------

  describe('Wait For Connection', () => {
    test('resolves immediately if already online', async () => {
      await NetworkDetector.initialize();
      
      const result = await NetworkDetector.waitForConnection(1000);
      expect(result).toBe(true);
    });

    test('waits for connection and resolves when online', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        isConnected: false,
      }));
      
      await NetworkDetector.initialize();
      
      const waitPromise = NetworkDetector.waitForConnection(5000);
      
      // Simulate coming online after 100ms
      setTimeout(() => {
        networkChangeCallback!(mockNetInfoState({ isConnected: true }));
      }, 100);
      
      const result = await waitPromise;
      expect(result).toBe(true);
    });

    test('times out and returns false if connection not restored', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        isConnected: false,
      }));
      
      await NetworkDetector.initialize();
      
      const result = await NetworkDetector.waitForConnection(100);
      expect(result).toBe(false);
    }, 1000);
  });

  // ---------------------------------------------------------------------------
  // Cleanup Tests
  // ---------------------------------------------------------------------------

  describe('Cleanup', () => {
    test('cleans up subscriptions on cleanup', async () => {
      const unsubscribe = jest.fn();
      (NetInfo.addEventListener as jest.Mock).mockReturnValue(unsubscribe);
      
      await NetworkDetector.initialize();
      NetworkDetector.cleanup();
      
      expect(unsubscribe).toHaveBeenCalled();
    });

    test('clears all subscribers on cleanup', async () => {
      await NetworkDetector.initialize();
      
      const callback = jest.fn();
      NetworkDetector.onChange(callback);
      
      NetworkDetector.cleanup();
      
      // Re-initialize and trigger change
      await NetworkDetector.initialize();
      networkChangeCallback!(mockNetInfoState({ isConnected: false }));
      
      // Old callback should not be called
      expect(callback).not.toHaveBeenCalled();
    });

    test('allows re-initialization after cleanup', async () => {
      await NetworkDetector.initialize();
      NetworkDetector.cleanup();
      
      // Should not throw
      await expect(NetworkDetector.initialize()).resolves.not.toThrow();
    });
  });

  // ---------------------------------------------------------------------------
  // Edge Cases
  // ---------------------------------------------------------------------------

  describe('Edge Cases', () => {
    test('handles null isInternetReachable', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValue(mockNetInfoState({
        isConnected: true,
        isInternetReachable: null,
      }));
      
      await NetworkDetector.initialize();
      
      const status = NetworkDetector.getStatus();
      expect(status.isInternetReachable).toBeNull();
      expect(status.isOnline).toBe(true);
    });

    test('handles rapid status changes', async () => {
      await NetworkDetector.initialize();
      
      const callback = jest.fn();
      NetworkDetector.onChange(callback);
      
      // Rapid changes
      networkChangeCallback!(mockNetInfoState({ isConnected: false }));
      networkChangeCallback!(mockNetInfoState({ isConnected: true }));
      networkChangeCallback!(mockNetInfoState({ isConnected: false }));
      
      expect(callback).toHaveBeenCalledTimes(3);
    });

    test('onChange triggers initialization if not initialized', () => {
      const callback = jest.fn();
      NetworkDetector.onChange(callback);
      
      // Initialize should have been triggered
      expect(NetInfo.fetch).toHaveBeenCalled();
    });
  });
});
