/**
 * API client with authentication and automatic token refresh.
 * 
 * Features:
 * - Automatic JWT token inclusion in requests
 * - Token refresh on 401 errors
 * - Request/response interceptors
 * - Type-safe API calls
 * - Configurable timeout and base URL
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '../stores/authStore';

// API base URL from environment variable
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance with default configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout for AI processing
  headers: {
    'Content-Type': 'application/json',
  },
});

// Flag to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

/**
 * Process queued requests after token refresh
 */
const processQueue = (error: AxiosError | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

/**
 * Request interceptor - Add JWT token to all requests
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const accessToken = useAuthStore.getState().accessToken;
    
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    
    // Log request in development
    if (process.env.REACT_APP_ENV === 'development') {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    }
    
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor - Handle token refresh on 401 errors
 */
apiClient.interceptors.response.use(
  (response) => {
    // Log response in development
    if (process.env.REACT_APP_ENV === 'development') {
      console.log(`[API] Response ${response.status} from ${response.config.url}`);
    }
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    
    // If not a 401 error, or already retried, reject immediately
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }
    
    // Check if this is a login request (don't refresh for login failures)
    if (originalRequest.url?.includes('/auth/login')) {
      return Promise.reject(error);
    }
    
    // If already refreshing, queue this request
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        })
        .catch((err) => {
          return Promise.reject(err);
        });
    }
    
    originalRequest._retry = true;
    isRefreshing = true;
    
    try {
      const refreshToken = useAuthStore.getState().refreshToken;
      
      if (!refreshToken) {
        // No refresh token available, logout
        useAuthStore.getState().logout();
        window.location.href = '/login';
        return Promise.reject(error);
      }
      
      // Attempt token refresh (use plain axios to avoid interceptor loop)
      const response = await axios.post(
        `${API_BASE_URL}/auth/refresh`,
        { refresh_token: refreshToken },
        { headers: { 'Content-Type': 'application/json' } }
      );
      
      const { access_token, refresh_token: newRefreshToken } = response.data;
      
      // Update tokens in store
      useAuthStore.getState().setTokens(access_token, newRefreshToken || refreshToken);
      
      // Process queued requests with new token
      processQueue(null, access_token);
      
      // Retry original request with new token
      originalRequest.headers.Authorization = `Bearer ${access_token}`;
      return apiClient(originalRequest);
      
    } catch (refreshError) {
      // Refresh failed, process queue with error and logout
      processQueue(refreshError as AxiosError, null);
      useAuthStore.getState().logout();
      window.location.href = '/login';
      return Promise.reject(refreshError);
      
    } finally {
      isRefreshing = false;
    }
  }
);

export default apiClient;

// Export base URL for external use
export { API_BASE_URL };
