/**
 * Unauthorized page component.
 * 
 * Shown when a user tries to access a page they don't have permission for.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

export const UnauthorizedPage: React.FC = () => {
  const { user } = useAuthStore();
  
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center">
        <div className="text-6xl mb-4">🚫</div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Access Denied</h1>
        <p className="text-gray-500 mb-6 max-w-md">
          You don't have permission to access this page.
          {user && (
            <span className="block mt-2 text-sm">
              Your current role: <span className="font-medium capitalize">{user.role}</span>
            </span>
          )}
        </p>
        <Link to="/dashboard" className="btn-primary">
          Return to Dashboard
        </Link>
      </div>
    </div>
  );
};

export default UnauthorizedPage;
