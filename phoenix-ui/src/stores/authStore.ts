/**
 * Authentication state management with Zustand.
 * 
 * Manages:
 * - User login/logout state
 * - JWT token storage (localStorage persistence)
 * - User profile information
 * - Role-based permission checking
 * 
 * The store automatically persists to localStorage and rehydrates on app load.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

/**
 * User role types matching backend UserRole enum
 */
export type UserRole = 'admin' | 'physician' | 'nurse' | 'scribe' | 'auditor' | 'readonly';

/**
 * User profile interface
 */
export interface User {
  id: number;
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  npiNumber?: string | null;
  licenseNumber?: string | null;
  licenseState?: string | null;
  isActive: boolean;
  createdAt?: string;
}

/**
 * Authentication state interface
 */
interface AuthState {
  // State
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Actions
  login: (accessToken: string, refreshToken: string, user: User) => void;
  logout: () => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  setAccessToken: (token: string) => void;
  setUser: (user: User) => void;
  setLoading: (loading: boolean) => void;
  
  // Permission helpers
  hasRole: (role: UserRole) => boolean;
  hasAnyRole: (roles: UserRole[]) => boolean;
  canEditEncounters: () => boolean;
  canSignNotes: () => boolean;
  canViewAuditLogs: () => boolean;
  canCreateEncounters: () => boolean;
  getFullName: () => string;
}

/**
 * Role hierarchy for permission checking.
 * Higher number = more permissions.
 */
const ROLE_HIERARCHY: Record<UserRole, number> = {
  admin: 6,
  physician: 5,
  nurse: 4,
  scribe: 3,
  auditor: 2,
  readonly: 1,
};

/**
 * Zustand auth store with localStorage persistence
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      
      /**
       * Login action - stores tokens and user info
       */
      login: (accessToken, refreshToken, user) => {
        set({
          accessToken,
          refreshToken,
          user,
          isAuthenticated: true,
          isLoading: false,
        });
      },
      
      /**
       * Logout action - clears all auth state
       */
      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          isLoading: false,
        });
      },
      
      /**
       * Update both tokens (after refresh)
       */
      setTokens: (accessToken, refreshToken) => {
        set({ accessToken, refreshToken });
      },
      
      /**
       * Update access token only
       */
      setAccessToken: (token) => {
        set({ accessToken: token });
      },
      
      /**
       * Update user profile
       */
      setUser: (user) => {
        set({ user });
      },
      
      /**
       * Set loading state
       */
      setLoading: (loading) => {
        set({ isLoading: loading });
      },
      
      /**
       * Check if user has at least the specified role
       */
      hasRole: (role) => {
        const currentRole = get().user?.role;
        if (!currentRole) return false;
        return ROLE_HIERARCHY[currentRole] >= ROLE_HIERARCHY[role];
      },
      
      /**
       * Check if user has any of the specified roles
       */
      hasAnyRole: (roles) => {
        const currentRole = get().user?.role;
        if (!currentRole) return false;
        return roles.some((role) => ROLE_HIERARCHY[currentRole] >= ROLE_HIERARCHY[role]);
      },
      
      /**
       * Check if user can edit encounters (physician, nurse, admin)
       */
      canEditEncounters: () => {
        return get().hasAnyRole(['physician', 'nurse', 'admin']);
      },
      
      /**
       * Check if user can sign notes (physician, admin only)
       */
      canSignNotes: () => {
        return get().hasAnyRole(['physician', 'admin']);
      },
      
      /**
       * Check if user can view audit logs (auditor, admin)
       */
      canViewAuditLogs: () => {
        return get().hasAnyRole(['auditor', 'admin']);
      },
      
      /**
       * Check if user can create new encounters (physician, admin)
       */
      canCreateEncounters: () => {
        return get().hasAnyRole(['physician', 'admin']);
      },
      
      /**
       * Get user's full name
       */
      getFullName: () => {
        const user = get().user;
        if (!user) return '';
        return `${user.firstName} ${user.lastName}`;
      },
    }),
    {
      name: 'phoenix-auth-storage', // localStorage key
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // Only persist these fields to localStorage
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

/**
 * Helper hook to get just the user
 */
export const useUser = () => useAuthStore((state) => state.user);

/**
 * Helper hook to check authentication status
 */
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated);

/**
 * Helper hook to get auth loading state
 */
export const useAuthLoading = () => useAuthStore((state) => state.isLoading);
