/**
 * Login page component.
 * 
 * Handles user authentication with email and password.
 * Uses React Query for API mutation management.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { authService, transformUserResponse } from '../api/services/authService';
import { useAuthStore } from '../stores/authStore';
import { LoadingSpinner } from '../components/LoadingSpinner';
import logoImg from '../assets/logo.png';

interface LocationState {
  from?: { pathname: string };
}

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, user: currentUser } = useAuthStore();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  // Get the page user tried to visit before being redirected to login
  const explicitFrom = (location.state as LocationState)?.from?.pathname;

  /**
   * Compute role-aware default redirect.
   * If the user was trying to reach a specific page, honour that (unless it's a
   * cross-role path). Otherwise redirect admin→/admin, others→/dashboard.
   */
  const getRedirectPath = useCallback((role: string) => {
    if (explicitFrom && explicitFrom !== '/') {
      // Don't send admin to clinical routes, or physician to admin routes
      if (role === 'admin' && !explicitFrom.startsWith('/admin')) return '/admin';
      if (role !== 'admin' && explicitFrom.startsWith('/admin')) return '/dashboard';
      return explicitFrom;
    }
    return role === 'admin' ? '/admin' : '/dashboard';
  }, [explicitFrom]);
  
  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && currentUser) {
      navigate(getRedirectPath(currentUser.role), { replace: true });
    }
  }, [isAuthenticated, currentUser, navigate, getRedirectPath]);
  
  // Login mutation
  const loginMutation = useMutation({
    mutationFn: authService.login,
    onSuccess: (data) => {
      const user = transformUserResponse(data.user);
      login(data.access_token, data.refresh_token, user);
      navigate(getRedirectPath(user.role), { replace: true });
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
    <div
      className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8"
      style={{ background: 'linear-gradient(135deg, var(--bg-deep) 0%, var(--bg-base) 50%, #0c1929 100%)' }}
    >
      <div className="max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <img src={logoImg} alt="Phoenix Guardian" className="h-28 w-28 object-contain drop-shadow-lg" />
          </div>
          <h1
            className="text-3xl font-bold"
            style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
          >
            Phoenix Guardian
          </h1>
          <p className="mt-2" style={{ color: 'var(--text-secondary)' }}>
            AI-Powered Medical Documentation
          </p>
        </div>
        
        {/* Login Card */}
        <div className="pg-card" style={{ padding: '28px' }}>
          <h2
            className="text-xl font-semibold mb-6"
            style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
          >
            Sign in to your account
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Error Alert */}
            {error && (
              <div
                className="px-4 py-3 rounded-lg text-sm"
                style={{
                  background: 'var(--critical-bg)',
                  border: '1px solid var(--critical-border)',
                  color: 'var(--critical-text)',
                }}
              >
                {error}
              </div>
            )}
            
            {/* Email Input */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium mb-1"
                style={{ color: 'var(--text-secondary)' }}
              >
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
              <label
                htmlFor="password"
                className="block text-sm font-medium mb-1"
                style={{ color: 'var(--text-secondary)' }}
              >
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
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Protected by Phoenix Guardian Security
            </p>
          </div>
        </div>
        
        {/* Demo credentials — click to auto-fill */}
        <div
          className="mt-4 rounded-lg"
          style={{
            padding: '16px',
            background: 'var(--zebra-glow)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
          }}
        >
          <p className="text-sm font-medium mb-2" style={{ color: 'var(--zebra-primary)' }}>
            Demo Credentials{' '}
            <span className="text-xs font-normal" style={{ color: 'var(--text-muted)' }}>(click to fill)</span>
          </p>
          <div className="space-y-1.5">
            <button
              type="button"
              onClick={() => { setEmail('admin@phoenixguardian.health'); setPassword('Admin123!'); }}
              className="w-full text-left text-xs rounded px-2 py-1 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(245,158,11,0.1)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <strong style={{ color: 'var(--zebra-primary)' }}>Admin:</strong> admin@phoenixguardian.health / Admin123!
            </button>
            <button
              type="button"
              onClick={() => { setEmail('dr.smith@phoenixguardian.health'); setPassword('Doctor123!'); }}
              className="w-full text-left text-xs rounded px-2 py-1 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(245,158,11,0.1)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <strong style={{ color: 'var(--zebra-primary)' }}>Physician:</strong> dr.smith@phoenixguardian.health / Doctor123!
            </button>
            <button
              type="button"
              onClick={() => { setEmail('nurse.jones@phoenixguardian.health'); setPassword('Nurse123!'); }}
              className="w-full text-left text-xs rounded px-2 py-1 transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(245,158,11,0.1)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <strong style={{ color: 'var(--zebra-primary)' }}>Nurse:</strong> nurse.jones@phoenixguardian.health / Nurse123!
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
