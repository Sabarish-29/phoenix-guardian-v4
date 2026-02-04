/**
 * Login page component.
 * 
 * Handles user authentication with email and password.
 * Uses React Query for API mutation management.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { authService, transformUserResponse } from '../api/services/authService';
import { useAuthStore } from '../stores/authStore';
import { LoadingSpinner } from '../components/LoadingSpinner';

interface LocationState {
  from?: { pathname: string };
}

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated } = useAuthStore();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  // Get the page user tried to visit before being redirected to login
  const from = (location.state as LocationState)?.from?.pathname || '/dashboard';
  
  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);
  
  // Login mutation
  const loginMutation = useMutation({
    mutationFn: authService.login,
    onSuccess: (data) => {
      const user = transformUserResponse(data.user);
      login(data.access_token, data.refresh_token, user);
      navigate(from, { replace: true });
    },
    onError: (err: Error & { response?: { data?: { detail?: string | Array<{msg: string}> } } }) => {
      const detail = err.response?.data?.detail;
      let message = 'Invalid email or password';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        // Handle Pydantic validation errors
        message = detail.map(e => e.msg).join(', ');
      }
      setError(message);
    },
  });
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    if (!email || !password) {
      setError('Please enter both email and password');
      return;
    }
    
    loginMutation.mutate({ username: email, password });
  };
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <span className="text-6xl">🏥</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Phoenix Guardian</h1>
          <p className="mt-2 text-gray-600">AI-Powered Medical Documentation</p>
        </div>
        
        {/* Login Card */}
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">Sign in to your account</h2>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Error Alert */}
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}
            
            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                placeholder="you@example.com"
                disabled={loginMutation.isPending}
              />
            </div>
            
            {/* Password Input */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="••••••••"
                disabled={loginMutation.isPending}
              />
            </div>
            
            {/* Submit Button */}
            <button
              type="submit"
              disabled={loginMutation.isPending}
              className="w-full btn-primary flex justify-center items-center"
            >
              {loginMutation.isPending ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
          
          {/* Footer */}
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-500">
              Protected by Phoenix Guardian Security
            </p>
          </div>
        </div>
        
        {/* Demo credentials (for development) */}
        {process.env.NODE_ENV === 'development' && (
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm font-medium text-yellow-800 mb-2">Demo Credentials:</p>
            <p className="text-xs text-yellow-700">
              <strong>Admin:</strong> admin@phoenixguardian.health / Admin123!<br />
              <strong>Physician:</strong> dr.smith@phoenixguardian.health / Doctor123!<br />
              <strong>Nurse:</strong> nurse.jones@phoenixguardian.health / Nurse123!
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginPage;
