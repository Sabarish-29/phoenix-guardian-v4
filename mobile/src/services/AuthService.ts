/**
 * Phoenix Guardian Mobile - Authentication Service
 * 
 * Handles JWT authentication with secure token storage.
 * 
 * Features:
 * - Login with hospital credentials
 * - Secure token storage (iOS Keychain / Android Keystore)
 * - Automatic token refresh
 * - Biometric authentication support
 * - Auto-logout on inactivity
 * 
 * @module services/AuthService
 */

import * as Keychain from 'react-native-keychain';
import axios, { AxiosInstance } from 'axios';
import { Platform } from 'react-native';
import { MMKV } from 'react-native-mmkv';

// ============================================================================
// Types & Interfaces
// ============================================================================

export interface LoginCredentials {
  tenantId: string;
  username: string;
  password: string;
}

export interface AuthToken {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;  // Unix timestamp in milliseconds
}

export interface UserInfo {
  userId: string;
  tenantId: string;
  username: string;
  displayName: string;
  role: 'physician' | 'nurse' | 'admin';
  permissions: string[];
}

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserInfo | null;
  error: string | null;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: UserInfo;
}

// ============================================================================
// Constants
// ============================================================================

const KEYCHAIN_SERVICE = 'com.phoenixguardian.mobile.auth';
const TOKEN_REFRESH_BUFFER = 5 * 60 * 1000;  // Refresh 5 minutes before expiry
const INACTIVITY_TIMEOUT = 30 * 60 * 1000;   // 30 minutes
const MAX_REFRESH_RETRIES = 3;

// Local storage for non-sensitive data
const storage = new MMKV({ id: 'phoenix-guardian-auth' });

// ============================================================================
// AuthService Class
// ============================================================================

class AuthService {
  private static instance: AuthService;
  private apiClient: AxiosInstance;
  private refreshPromise: Promise<AuthToken | null> | null = null;
  private lastActivityTime: number = Date.now();
  private inactivityTimer: ReturnType<typeof setTimeout> | null = null;
  private onLogoutCallback: (() => void) | null = null;

  private constructor() {
    const baseURL = __DEV__ 
      ? 'http://localhost:8000/api'
      : 'https://api.phoenix-guardian.ai';
    
    this.apiClient = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include auth token
    this.apiClient.interceptors.request.use(
      async (config) => {
        const token = await this.getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Add response interceptor for 401 handling
    this.apiClient.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          await this.logout();
        }
        return Promise.reject(error);
      }
    );
  }

  static getInstance(): AuthService {
    if (!AuthService.instance) {
      AuthService.instance = new AuthService();
    }
    return AuthService.instance;
  }

  // ==========================================================================
  // Authentication Methods
  // ==========================================================================

  /**
   * Login with credentials and store tokens securely.
   */
  async login(credentials: LoginCredentials): Promise<UserInfo> {
    try {
      const response = await this.apiClient.post<LoginResponse>('/auth/login', {
        tenant_id: credentials.tenantId,
        username: credentials.username,
        password: credentials.password,
        device_type: Platform.OS,
        device_id: await this.getDeviceId(),
      });

      const { access_token, refresh_token, expires_in, user } = response.data;

      // Store tokens securely in Keychain/Keystore
      await this.storeTokens({
        accessToken: access_token,
        refreshToken: refresh_token,
        expiresAt: Date.now() + (expires_in * 1000),
      });

      // Store user info in local storage
      storage.set('user_info', JSON.stringify(user));
      storage.set('tenant_id', credentials.tenantId);

      // Start inactivity monitoring
      this.startInactivityMonitor();

      return user;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 401) {
          throw new Error('Invalid credentials');
        }
        if (error.response?.status === 403) {
          throw new Error('Account suspended. Contact administrator.');
        }
        if (!error.response) {
          throw new Error('Network error. Check your connection.');
        }
      }
      throw new Error('Login failed. Please try again.');
    }
  }

  /**
   * Logout and clear all stored credentials.
   */
  async logout(): Promise<void> {
    try {
      // Attempt to notify server (best effort)
      const token = await this.getTokenWithoutRefresh();
      if (token) {
        await this.apiClient.post('/auth/logout').catch(() => {});
      }
    } finally {
      // Clear all stored data
      await Keychain.resetGenericPassword({ service: KEYCHAIN_SERVICE });
      storage.delete('user_info');
      storage.delete('tenant_id');
      
      // Stop inactivity monitor
      this.stopInactivityMonitor();
      
      // Notify app of logout
      if (this.onLogoutCallback) {
        this.onLogoutCallback();
      }
    }
  }

  /**
   * Check if user is authenticated with valid token.
   */
  async isAuthenticated(): Promise<boolean> {
    const token = await this.getToken();
    return token !== null;
  }

  /**
   * Get current access token, refreshing if needed.
   */
  async getToken(): Promise<string | null> {
    try {
      const tokens = await this.getStoredTokens();
      if (!tokens) {
        return null;
      }

      // Check if token is expired or expiring soon
      const needsRefresh = tokens.expiresAt < Date.now() + TOKEN_REFRESH_BUFFER;
      
      if (needsRefresh) {
        const newTokens = await this.refreshTokens(tokens.refreshToken);
        return newTokens?.accessToken || null;
      }

      return tokens.accessToken;
    } catch (error) {
      console.error('Failed to get token:', error);
      return null;
    }
  }

  /**
   * Get token without attempting refresh (for logout).
   */
  private async getTokenWithoutRefresh(): Promise<string | null> {
    try {
      const tokens = await this.getStoredTokens();
      return tokens?.accessToken || null;
    } catch {
      return null;
    }
  }

  /**
   * Get stored user info.
   */
  getUserInfo(): UserInfo | null {
    const userJson = storage.getString('user_info');
    if (!userJson) {
      return null;
    }
    try {
      return JSON.parse(userJson);
    } catch {
      return null;
    }
  }

  /**
   * Get current tenant ID.
   */
  getTenantId(): string | null {
    return storage.getString('tenant_id') || null;
  }

  // ==========================================================================
  // Token Management
  // ==========================================================================

  /**
   * Store tokens securely in Keychain/Keystore.
   */
  private async storeTokens(tokens: AuthToken): Promise<void> {
    const biometryType = await Keychain.getSupportedBiometryType();
    
    const options: Keychain.SetOptions = {
      service: KEYCHAIN_SERVICE,
      accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    };

    // Enable biometric protection if available
    if (biometryType) {
      options.accessControl = Keychain.ACCESS_CONTROL.BIOMETRY_ANY_OR_DEVICE_PASSCODE;
    }

    await Keychain.setGenericPassword(
      'phoenix_guardian_tokens',
      JSON.stringify(tokens),
      options
    );
  }

  /**
   * Retrieve stored tokens from Keychain/Keystore.
   */
  private async getStoredTokens(): Promise<AuthToken | null> {
    try {
      const credentials = await Keychain.getGenericPassword({
        service: KEYCHAIN_SERVICE,
      });

      if (!credentials || typeof credentials === 'boolean') {
        return null;
      }

      return JSON.parse(credentials.password);
    } catch (error) {
      console.error('Failed to get stored tokens:', error);
      return null;
    }
  }

  /**
   * Refresh access token using refresh token.
   * Uses mutex to prevent concurrent refresh attempts.
   */
  private async refreshTokens(refreshToken: string): Promise<AuthToken | null> {
    // If already refreshing, wait for that promise
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = this.doRefreshTokens(refreshToken);
    
    try {
      return await this.refreshPromise;
    } finally {
      this.refreshPromise = null;
    }
  }

  /**
   * Actual token refresh logic with retries.
   */
  private async doRefreshTokens(refreshToken: string, retries = 0): Promise<AuthToken | null> {
    try {
      const response = await this.apiClient.post('/auth/refresh', {
        refresh_token: refreshToken,
      });

      const { access_token, refresh_token: newRefreshToken, expires_in } = response.data;

      const newTokens: AuthToken = {
        accessToken: access_token,
        refreshToken: newRefreshToken,
        expiresAt: Date.now() + (expires_in * 1000),
      };

      await this.storeTokens(newTokens);
      return newTokens;
    } catch (error) {
      if (retries < MAX_REFRESH_RETRIES && axios.isAxiosError(error) && !error.response) {
        // Network error - retry
        await new Promise(resolve => setTimeout(resolve, 1000 * (retries + 1)));
        return this.doRefreshTokens(refreshToken, retries + 1);
      }
      
      // Refresh failed - logout
      console.error('Token refresh failed:', error);
      await this.logout();
      return null;
    }
  }

  // ==========================================================================
  // Inactivity Management
  // ==========================================================================

  /**
   * Record user activity to reset inactivity timer.
   */
  recordActivity(): void {
    this.lastActivityTime = Date.now();
  }

  /**
   * Start monitoring for inactivity.
   */
  private startInactivityMonitor(): void {
    this.stopInactivityMonitor();
    
    this.inactivityTimer = setInterval(() => {
      const inactiveTime = Date.now() - this.lastActivityTime;
      if (inactiveTime > INACTIVITY_TIMEOUT) {
        console.log('User inactive - logging out');
        this.logout();
      }
    }, 60000); // Check every minute
  }

  /**
   * Stop inactivity monitoring.
   */
  private stopInactivityMonitor(): void {
    if (this.inactivityTimer) {
      clearInterval(this.inactivityTimer);
      this.inactivityTimer = null;
    }
  }

  /**
   * Set callback for logout events.
   */
  onLogout(callback: () => void): void {
    this.onLogoutCallback = callback;
  }

  // ==========================================================================
  // Device Management
  // ==========================================================================

  /**
   * Get unique device identifier.
   */
  private async getDeviceId(): Promise<string> {
    let deviceId = storage.getString('device_id');
    
    if (!deviceId) {
      // Generate new device ID
      const { v4: uuidv4 } = await import('uuid');
      deviceId = uuidv4();
      storage.set('device_id', deviceId);
    }
    
    return deviceId;
  }

  // ==========================================================================
  // Biometric Authentication
  // ==========================================================================

  /**
   * Check if biometric authentication is available.
   */
  async isBiometricAvailable(): Promise<boolean> {
    const biometryType = await Keychain.getSupportedBiometryType();
    return biometryType !== null;
  }

  /**
   * Get the type of biometric authentication available.
   */
  async getBiometryType(): Promise<string | null> {
    const biometryType = await Keychain.getSupportedBiometryType();
    return biometryType;
  }

  /**
   * Authenticate with biometrics.
   */
  async authenticateWithBiometrics(): Promise<boolean> {
    try {
      const credentials = await Keychain.getGenericPassword({
        service: KEYCHAIN_SERVICE,
        authenticationPrompt: {
          title: 'Authenticate',
          subtitle: 'Use biometrics to access Phoenix Guardian',
          cancel: 'Cancel',
        },
      });
      
      return credentials !== false;
    } catch (error) {
      console.error('Biometric authentication failed:', error);
      return false;
    }
  }

  // ==========================================================================
  // API Client Access
  // ==========================================================================

  /**
   * Get configured API client for other services.
   */
  getApiClient(): AxiosInstance {
    return this.apiClient;
  }
}

// Export singleton instance
export default AuthService.getInstance();
