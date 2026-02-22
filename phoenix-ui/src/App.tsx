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
import { LanguageProvider } from './context/LanguageContext';

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
  AdminHomePage,
  AdminReportsPage,
  AdminUsersPage,
  AdminAuditLogsPage,
  TreatmentShadowPage,
  SilentVoicePage,
  ZebraHunterPage,
  V5DashboardPage,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, isAuthenticated, logout, setLoading]);
  
  return <>{children}</>;
};

/**
 * Role-aware root redirect component.
 * Admin users go to /admin, everyone else goes to /dashboard.
 */
const RootRedirect: React.FC = () => {
  const { user, isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.role === 'admin') return <Navigate to="/admin" replace />;
  return <Navigate to="/v5-dashboard" replace />;
};

/**
 * Main App component
 */
const App: React.FC = () => {
  return (
    <LanguageProvider>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthInitializer>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            
            {/* ───── Clinical routes (physician, nurse — NOT admin) ───── */}
            <Route
              element={
                <ProtectedRoute excludeRoles={['admin']}>
                  <Layout />
                </ProtectedRoute>
              }
            >
              {/* V5 Dashboard - unified agent overview */}
              <Route path="/v5-dashboard" element={<V5DashboardPage />} />
              
              {/* Dashboard - clinical users only (legacy) */}
              <Route path="/dashboard" element={<DashboardPage />} />
              
              {/* SOAP Generator - physicians only */}
              <Route
                path="/soap-generator"
                element={
                  <ProtectedRoute requiredRoles={['physician']}>
                    <SOAPGeneratorPage />
                  </ProtectedRoute>
                }
              />
              
              {/* Encounters list */}
              <Route path="/encounters" element={<EncountersListPage />} />
              
              {/* Create encounter - physicians only */}
              <Route
                path="/encounters/new"
                element={
                  <ProtectedRoute requiredRoles={['physician']}>
                    <CreateEncounterPage />
                  </ProtectedRoute>
                }
              />
              
              {/* Treatment Shadow Monitor */}
              <Route path="/treatment-shadow" element={<TreatmentShadowPage />} />

              {/* Silent Voice Monitor */}
              <Route path="/silent-voice" element={<SilentVoicePage />} />

              {/* Zebra Hunter — Rare Disease Detector */}
              <Route path="/zebra-hunter" element={<ZebraHunterPage />} />

              {/* View encounter */}
              <Route path="/encounters/:uuid" element={<ReviewSOAPNotePage />} />
              
              {/* Review SOAP note - physicians only */}
              <Route
                path="/encounters/:uuid/review"
                element={
                  <ProtectedRoute requiredRoles={['physician']}>
                    <ReviewSOAPNotePage />
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* ───── Admin routes (admin only) ───── */}
            <Route
              element={
                <ProtectedRoute requiredRoles={['admin']}>
                  <Layout />
                </ProtectedRoute>
              }
            >
              {/* Admin home */}
              <Route path="/admin" element={<AdminHomePage />} />
              
              {/* Security console */}
              <Route path="/admin/security" element={<AdminSecurityConsolePage />} />
              
              {/* Reports */}
              <Route path="/admin/reports" element={<AdminReportsPage />} />
              
              {/* User management */}
              <Route path="/admin/users" element={<AdminUsersPage />} />
              
              {/* Audit logs */}
              <Route path="/admin/audit-logs" element={<AdminAuditLogsPage />} />
            </Route>

            {/* ───── Shared routes (all authenticated users) ───── */}
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
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
            </Route>
            
            {/* Role-aware root redirect */}
            <Route path="/" element={<RootRedirect />} />
            
            {/* 404 Not Found */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthInitializer>
      </BrowserRouter>
    </QueryClientProvider>
    </LanguageProvider>
  );
};

export default App;
