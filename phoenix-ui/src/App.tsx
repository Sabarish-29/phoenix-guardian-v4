/**
 * Main application component.
 * 
 * Sets up:
 * - React Query provider for API state management
 * - React Router for navigation
 * - Protected routes with role-based access
 * - Layout structure
 */

import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Components
import { Layout, ProtectedRoute } from './components';

// Pages
import {
  LoginPage,
  DashboardPage,
  CreateEncounterPage,
  ReviewSOAPNotePage,
  EncountersListPage,
  SOAPGeneratorPage,
  UnauthorizedPage,
  NotFoundPage,
  AdminSecurityConsolePage,
} from './pages';

// Store
import { useAuthStore } from './stores/authStore';
import { authService } from './api/services/authService';

/**
 * React Query client configuration
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

/**
 * Auth initializer component.
 * Validates stored token on app load.
 */
const AuthInitializer: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, accessToken, setUser, logout, setLoading } = useAuthStore();
  
  useEffect(() => {
    const validateAuth = async () => {
      if (isAuthenticated && accessToken) {
        setLoading(true);
        try {
          // Validate token by fetching current user
          const user = await authService.getCurrentUser();
          setUser(user);
        } catch (error) {
          // Token is invalid, log out
          console.warn('Token validation failed, logging out');
          logout();
        } finally {
          setLoading(false);
        }
      }
    };
    
    validateAuth();
  }, []);
  
  return <>{children}</>;
};

/**
 * Main App component
 */
const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthInitializer>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            
            {/* Protected routes with Layout */}
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              {/* Dashboard - accessible to all authenticated users */}
              <Route path="/dashboard" element={<DashboardPage />} />
              
              {/* SOAP Generator - physicians and admins */}
              <Route
                path="/soap-generator"
                element={
                  <ProtectedRoute requiredRoles={['physician', 'admin']}>
                    <SOAPGeneratorPage />
                  </ProtectedRoute>
                }
              />
              
              {/* Encounters list */}
              <Route path="/encounters" element={<EncountersListPage />} />
              
              {/* Create encounter - physicians and admins only */}
              <Route
                path="/encounters/new"
                element={
                  <ProtectedRoute requiredRoles={['physician', 'admin']}>
                    <CreateEncounterPage />
                  </ProtectedRoute>
                }
              />
              
              {/* View encounter */}
              <Route path="/encounters/:uuid" element={<ReviewSOAPNotePage />} />
              
              {/* Review SOAP note - physicians and admins only */}
              <Route
                path="/encounters/:uuid/review"
                element={
                  <ProtectedRoute requiredRoles={['physician', 'admin']}>
                    <ReviewSOAPNotePage />
                  </ProtectedRoute>
                }
              />
              
              {/* Unauthorized page */}
              <Route path="/unauthorized" element={<UnauthorizedPage />} />
              
              {/* Profile page (placeholder) */}
              <Route
                path="/profile"
                element={
                  <div className="card">
                    <h1 className="text-2xl font-bold text-gray-900 mb-4">My Profile</h1>
                    <p className="text-gray-500">Profile management coming soon.</p>
                  </div>
                }
              />
              
              {/* Help page (placeholder) */}
              <Route
                path="/help"
                element={
                  <div className="card">
                    <h1 className="text-2xl font-bold text-gray-900 mb-4">Help & Support</h1>
                    <p className="text-gray-500">
                      For assistance, contact your system administrator or visit our documentation.
                    </p>
                  </div>
                }
              />
              
              {/* Admin Security Console - admin only */}
              <Route
                path="/admin/security"
                element={
                  <ProtectedRoute requiredRoles={['admin']}>
                    <AdminSecurityConsolePage />
                  </ProtectedRoute>
                }
              />

              {/* Audit logs - auditors and admins only */}
              <Route
                path="/audit"
                element={
                  <ProtectedRoute requiredRoles={['auditor', 'admin']}>
                    <div className="card">
                      <h1 className="text-2xl font-bold text-gray-900 mb-4">Audit Logs</h1>
                      <p className="text-gray-500">Audit log viewer coming soon.</p>
                    </div>
                  </ProtectedRoute>
                }
              />
            </Route>
            
            {/* Root redirect */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            
            {/* 404 Not Found */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthInitializer>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
