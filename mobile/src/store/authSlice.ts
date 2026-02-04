/**
 * Phoenix Guardian Mobile - Week 23-24
 * Auth Slice: Redux state for authentication.
 * 
 * Features:
 * - Login/logout state management
 * - User profile storage
 * - Token status tracking
 * - Hospital/tenant context
 */

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
interface User {
  id: string;
  email: string;
  name: string;
  role: 'physician' | 'nurse' | 'admin';
  hospitalId: string;
  hospitalName: string;
  department?: string;
  npi?: string;
}

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  tenantId: string | null;
  tokenExpiresAt: number | null;
  error: string | null;
  biometricEnabled: boolean;
  lastLoginAt: string | null;
}

interface LoginPayload {
  tenantId: string;
  username: string;
  password: string;
}

interface LoginResult {
  user: User;
  tenantId: string;
  expiresAt: number;
}

// Initial state
const initialState: AuthState = {
  isAuthenticated: false,
  isLoading: false,
  user: null,
  tenantId: null,
  tokenExpiresAt: null,
  error: null,
  biometricEnabled: false,
  lastLoginAt: null,
};

// Async thunks
export const login = createAsyncThunk<LoginResult, LoginPayload>(
  'auth/login',
  async (credentials, { rejectWithValue }) => {
    try {
      // In production, this would call AuthService.login()
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Simulate successful login
      const result: LoginResult = {
        user: {
          id: 'user_001',
          email: credentials.username,
          name: 'Dr. Sarah Chen',
          role: 'physician',
          hospitalId: credentials.tenantId,
          hospitalName: 'General Hospital',
          department: 'Internal Medicine',
          npi: '1234567890',
        },
        tenantId: credentials.tenantId,
        expiresAt: Date.now() + 3600000, // 1 hour
      };

      return result;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Login failed');
    }
  }
);

export const logout = createAsyncThunk(
  'auth/logout',
  async (_, { rejectWithValue }) => {
    try {
      // In production, this would call AuthService.logout()
      await new Promise(resolve => setTimeout(resolve, 300));
      return true;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Logout failed');
    }
  }
);

export const refreshToken = createAsyncThunk(
  'auth/refreshToken',
  async (_, { rejectWithValue }) => {
    try {
      // In production, this would call AuthService.refreshToken()
      await new Promise(resolve => setTimeout(resolve, 500));
      return {
        expiresAt: Date.now() + 3600000, // 1 hour
      };
    } catch (error: any) {
      return rejectWithValue(error.message || 'Token refresh failed');
    }
  }
);

export const checkAuthStatus = createAsyncThunk(
  'auth/checkStatus',
  async (_, { rejectWithValue }) => {
    try {
      // In production, this would check stored credentials
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Simulate no stored auth
      return null;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Auth check failed');
    }
  }
);

// Slice
const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    setBiometricEnabled: (state, action: PayloadAction<boolean>) => {
      state.biometricEnabled = action.payload;
    },
    updateUser: (state, action: PayloadAction<Partial<User>>) => {
      if (state.user) {
        state.user = { ...state.user, ...action.payload };
      }
    },
    setTokenExpiry: (state, action: PayloadAction<number>) => {
      state.tokenExpiresAt = action.payload;
    },
  },
  extraReducers: (builder) => {
    // Login
    builder.addCase(login.pending, (state) => {
      state.isLoading = true;
      state.error = null;
    });
    builder.addCase(login.fulfilled, (state, action) => {
      state.isLoading = false;
      state.isAuthenticated = true;
      state.user = action.payload.user;
      state.tenantId = action.payload.tenantId;
      state.tokenExpiresAt = action.payload.expiresAt;
      state.lastLoginAt = new Date().toISOString();
      state.error = null;
    });
    builder.addCase(login.rejected, (state, action) => {
      state.isLoading = false;
      state.isAuthenticated = false;
      state.error = action.payload as string;
    });

    // Logout
    builder.addCase(logout.pending, (state) => {
      state.isLoading = true;
    });
    builder.addCase(logout.fulfilled, (state) => {
      state.isLoading = false;
      state.isAuthenticated = false;
      state.user = null;
      state.tenantId = null;
      state.tokenExpiresAt = null;
      state.error = null;
    });
    builder.addCase(logout.rejected, (state, action) => {
      state.isLoading = false;
      state.error = action.payload as string;
      // Still clear auth on logout failure
      state.isAuthenticated = false;
      state.user = null;
    });

    // Refresh token
    builder.addCase(refreshToken.fulfilled, (state, action) => {
      state.tokenExpiresAt = action.payload.expiresAt;
    });
    builder.addCase(refreshToken.rejected, (state) => {
      // Force logout on refresh failure
      state.isAuthenticated = false;
      state.user = null;
      state.tokenExpiresAt = null;
    });

    // Check auth status
    builder.addCase(checkAuthStatus.pending, (state) => {
      state.isLoading = true;
    });
    builder.addCase(checkAuthStatus.fulfilled, (state, action) => {
      state.isLoading = false;
      if (action.payload) {
        state.isAuthenticated = true;
        state.user = action.payload.user;
        state.tenantId = action.payload.tenantId;
      }
    });
    builder.addCase(checkAuthStatus.rejected, (state) => {
      state.isLoading = false;
      state.isAuthenticated = false;
    });
  },
});

export const { clearError, setBiometricEnabled, updateUser, setTokenExpiry } = authSlice.actions;
export default authSlice.reducer;

// Selectors
export const selectIsAuthenticated = (state: { auth: AuthState }) => state.auth.isAuthenticated;
export const selectUser = (state: { auth: AuthState }) => state.auth.user;
export const selectTenantId = (state: { auth: AuthState }) => state.auth.tenantId;
export const selectAuthLoading = (state: { auth: AuthState }) => state.auth.isLoading;
export const selectAuthError = (state: { auth: AuthState }) => state.auth.error;
export const selectTokenExpiresAt = (state: { auth: AuthState }) => state.auth.tokenExpiresAt;
