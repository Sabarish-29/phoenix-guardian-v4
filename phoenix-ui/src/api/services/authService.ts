/**
 * Authentication API service.
 * 
 * Handles all authentication-related API calls:
 * - Login
 * - Token refresh
 * - Logout
 * - Get current user
 * - Password change
 */

import apiClient from '../client';
import type { User, UserRole } from '../../stores/authStore';

/**
 * Login request payload
 */
export interface LoginRequest {
  username: string;  // email
  password: string;
}

/**
 * Login response from API
 */
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserApiResponse;
}

/**
 * User response from API (snake_case)
 */
export interface UserApiResponse {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  npi_number: string | null;
  license_number: string | null;
  license_state: string | null;
  is_active: boolean;
  created_at: string;
}

/**
 * Token refresh request
 */
export interface RefreshRequest {
  refresh_token: string;
}

/**
 * Token refresh response
 */
export interface RefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

/**
 * Password change request
 */
export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

/**
 * Transform API user response to frontend User model
 */
export const transformUserResponse = (apiUser: UserApiResponse): User => ({
  id: apiUser.id,
  email: apiUser.email,
  firstName: apiUser.first_name,
  lastName: apiUser.last_name,
  role: apiUser.role,
  npiNumber: apiUser.npi_number,
  licenseNumber: apiUser.license_number,
  licenseState: apiUser.license_state,
  isActive: apiUser.is_active,
  createdAt: apiUser.created_at,
});

/**
 * Authentication service class
 */
export const authService = {
  /**
   * Login with email and password.
   * Returns tokens and user information.
   */
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    // Backend expects JSON with email and password
    const response = await apiClient.post<LoginResponse>('/auth/login', {
      email: credentials.username,  // Frontend uses 'username' but backend expects 'email'
      password: credentials.password,
    });
    
    return response.data;
  },
  
  /**
   * Refresh the access token using the refresh token.
   */
  async refreshToken(refreshToken: string): Promise<RefreshResponse> {
    const response = await apiClient.post<RefreshResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    
    return response.data;
  },
  
  /**
   * Get the current authenticated user's profile.
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<UserApiResponse>('/auth/me');
    return transformUserResponse(response.data);
  },
  
  /**
   * Logout the current user (invalidates refresh token on server).
   */
  async logout(): Promise<void> {
    await apiClient.post('/auth/logout');
  },
  
  /**
   * Change the current user's password.
   */
  async changePassword(data: ChangePasswordRequest): Promise<void> {
    await apiClient.post('/auth/change-password', {
      current_password: data.current_password,
      new_password: data.new_password,
    });
  },
  
  /**
   * Validate if the current access token is valid.
   */
  async validateToken(): Promise<boolean> {
    try {
      await apiClient.get('/auth/me');
      return true;
    } catch {
      return false;
    }
  },
};

export default authService;
