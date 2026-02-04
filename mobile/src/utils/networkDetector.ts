/**
 * Network connectivity detection utility.
 * 
 * Features:
 * - Real-time network status monitoring
 * - Callback-based change notifications
 * - Ping-based connectivity verification
 * - Automatic retry logic
 */

import NetInfo, { NetInfoState, NetInfoSubscription } from '@react-native-community/netinfo';

// =============================================================================
// TYPES
// =============================================================================

type NetworkChangeCallback = (isOnline: boolean) => void;

interface NetworkStatus {
  isOnline: boolean;
  isInternetReachable: boolean | null;
  type: string;
  isWifi: boolean;
  isCellular: boolean;
  details: NetInfoState | null;
}

// =============================================================================
// NETWORK DETECTOR CLASS
// =============================================================================

class NetworkDetector {
  private static instance: NetworkDetector;
  private subscribers: Set<NetworkChangeCallback> = new Set();
  private subscription: NetInfoSubscription | null = null;
  private currentStatus: NetworkStatus = {
    isOnline: true,
    isInternetReachable: null,
    type: 'unknown',
    isWifi: false,
    isCellular: false,
    details: null,
  };
  private initialized: boolean = false;
  
  // Ping configuration for connectivity verification
  private readonly PING_URL = 'https://api.phoenix-guardian.health/health';
  private readonly PING_TIMEOUT = 5000;
  
  private constructor() {}
  
  /**
   * Get singleton instance.
   */
  static getInstance(): NetworkDetector {
    if (!NetworkDetector.instance) {
      NetworkDetector.instance = new NetworkDetector();
    }
    return NetworkDetector.instance;
  }
  
  /**
   * Initialize network monitoring.
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;
    
    try {
      // Get initial state
      const state = await NetInfo.fetch();
      this.updateStatus(state);
      
      // Subscribe to changes
      this.subscription = NetInfo.addEventListener((state) => {
        this.updateStatus(state);
      });
      
      this.initialized = true;
      console.log('[NetworkDetector] Initialized:', this.currentStatus);
    } catch (error) {
      console.error('[NetworkDetector] Initialization failed:', error);
      // Default to online if we can't detect
      this.currentStatus.isOnline = true;
    }
  }
  
  /**
   * Update internal status and notify subscribers.
   */
  private updateStatus(state: NetInfoState): void {
    const wasOnline = this.currentStatus.isOnline;
    
    this.currentStatus = {
      isOnline: state.isConnected ?? false,
      isInternetReachable: state.isInternetReachable,
      type: state.type,
      isWifi: state.type === 'wifi',
      isCellular: state.type === 'cellular',
      details: state,
    };
    
    // Only notify if status changed
    if (wasOnline !== this.currentStatus.isOnline) {
      console.log('[NetworkDetector] Status changed:', {
        wasOnline,
        isOnline: this.currentStatus.isOnline,
        type: this.currentStatus.type,
      });
      
      this.notifySubscribers(this.currentStatus.isOnline);
    }
  }
  
  /**
   * Notify all subscribers of status change.
   */
  private notifySubscribers(isOnline: boolean): void {
    this.subscribers.forEach((callback) => {
      try {
        callback(isOnline);
      } catch (error) {
        console.error('[NetworkDetector] Subscriber callback error:', error);
      }
    });
  }
  
  /**
   * Check if currently online.
   * For critical operations, use verifyConnectivity() instead.
   */
  async isOnline(): Promise<boolean> {
    if (!this.initialized) {
      await this.initialize();
    }
    return this.currentStatus.isOnline;
  }
  
  /**
   * Check if currently online (synchronous version).
   * May not reflect the most current state.
   */
  isOnlineSync(): boolean {
    return this.currentStatus.isOnline;
  }
  
  /**
   * Get current network status.
   */
  getStatus(): NetworkStatus {
    return { ...this.currentStatus };
  }
  
  /**
   * Subscribe to network changes.
   * Returns unsubscribe function.
   */
  onChange(callback: NetworkChangeCallback): () => void {
    this.subscribers.add(callback);
    
    // Initialize if not already done
    if (!this.initialized) {
      this.initialize();
    }
    
    // Return unsubscribe function
    return () => {
      this.subscribers.delete(callback);
    };
  }
  
  /**
   * Verify actual internet connectivity by making a request.
   * More reliable than just checking connection status.
   */
  async verifyConnectivity(): Promise<boolean> {
    if (!this.currentStatus.isOnline) {
      return false;
    }
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.PING_TIMEOUT);
      
      const response = await fetch(this.PING_URL, {
        method: 'HEAD',
        signal: controller.signal,
        cache: 'no-cache',
      });
      
      clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      console.warn('[NetworkDetector] Connectivity verification failed:', error);
      return false;
    }
  }
  
  /**
   * Wait for network to become available.
   * Useful for retry logic.
   */
  async waitForConnection(timeoutMs: number = 30000): Promise<boolean> {
    if (await this.isOnline()) {
      return true;
    }
    
    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        unsubscribe();
        resolve(false);
      }, timeoutMs);
      
      const unsubscribe = this.onChange((isOnline) => {
        if (isOnline) {
          clearTimeout(timeout);
          unsubscribe();
          resolve(true);
        }
      });
    });
  }
  
  /**
   * Get connection type (wifi, cellular, etc.).
   */
  getConnectionType(): string {
    return this.currentStatus.type;
  }
  
  /**
   * Check if on WiFi (preferred for large uploads).
   */
  isOnWifi(): boolean {
    return this.currentStatus.isWifi;
  }
  
  /**
   * Check if on cellular (may have data limits).
   */
  isOnCellular(): boolean {
    return this.currentStatus.isCellular;
  }
  
  /**
   * Clean up subscriptions.
   */
  cleanup(): void {
    if (this.subscription) {
      this.subscription();
      this.subscription = null;
    }
    this.subscribers.clear();
    this.initialized = false;
  }
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

const networkDetector = NetworkDetector.getInstance();

// Export both the instance and convenient static-like methods
export default {
  initialize: () => networkDetector.initialize(),
  isOnline: () => networkDetector.isOnline(),
  isOnlineSync: () => networkDetector.isOnlineSync(),
  getStatus: () => networkDetector.getStatus(),
  onChange: (callback: NetworkChangeCallback) => networkDetector.onChange(callback),
  verifyConnectivity: () => networkDetector.verifyConnectivity(),
  waitForConnection: (timeoutMs?: number) => networkDetector.waitForConnection(timeoutMs),
  getConnectionType: () => networkDetector.getConnectionType(),
  isOnWifi: () => networkDetector.isOnWifi(),
  isOnCellular: () => networkDetector.isOnCellular(),
  cleanup: () => networkDetector.cleanup(),
};

export { NetworkDetector, NetworkStatus, NetworkChangeCallback };
