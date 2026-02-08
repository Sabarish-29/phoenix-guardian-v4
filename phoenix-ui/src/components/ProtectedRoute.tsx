/**
 * Protected route component.
 * 
 * Wraps routes that require authentication and optionally specific roles.
 * Redirects to login if not authenticated, or to unauthorized page if lacking permissions.
 */

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import type { UserRole } from '../stores/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: UserRole;
  requiredRoles?: UserRole[];
  excludeRoles?: UserRole[];
  fallbackPath?: string;
}

/**
 * ProtectedRoute component
 * 
 * @param children - The protected content to render
 * @param requiredRole - Single role required (uses hasRole which checks hierarchy)
 * @param requiredRoles - Multiple roles, user must have at least one
 * @param excludeRoles - Roles that are explicitly denied access (exact match, bypasses hierarchy)
 * @param fallbackPath - Where to redirect if unauthorized (default: /unauthorized)
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole,
  requiredRoles,
  excludeRoles,
  fallbackPath = '/unauthorized',
}) => {
  const location = useLocation();
  const { isAuthenticated, user, hasRole, hasAnyRole, isLoading } = useAuthStore();
  
  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }
  
  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    // Save the attempted location for redirect after login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  
  // Explicitly deny excluded roles (bypasses hierarchy, exact role match)
  if (excludeRoles && user?.role && excludeRoles.includes(user.role)) {
    return <Navigate to={fallbackPath} replace />;
  }
  
  // Check role permissions if specified
  if (requiredRole && !hasRole(requiredRole)) {
    return <Navigate to={fallbackPath} replace />;
  }
  
  if (requiredRoles && requiredRoles.length > 0 && !hasAnyRole(requiredRoles)) {
    return <Navigate to={fallbackPath} replace />;
  }
  
  // User is authenticated and has required permissions
  return <>{children}</>;
};

/**
 * Higher-order component version for class components
 */
export function withProtectedRoute<P extends object>(
  Component: React.ComponentType<P>,
  options?: {
    requiredRole?: UserRole;
    requiredRoles?: UserRole[];
    fallbackPath?: string;
  }
) {
  return function ProtectedComponent(props: P) {
    return (
      <ProtectedRoute {...options}>
        <Component {...props} />
      </ProtectedRoute>
    );
  };
}

export default ProtectedRoute;
