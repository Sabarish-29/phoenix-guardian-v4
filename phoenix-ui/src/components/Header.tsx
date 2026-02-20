/**
 * Application header/navigation component.
 */

import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import logoImg from '../assets/logo.png';

export const Header: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, user, logout, getFullName, canCreateEncounters } = useAuthStore();
  
  const handleLogout = () => {
    logout();
    navigate('/login');
  };
  
  if (!isAuthenticated) {
    return (
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <Link to="/" className="flex items-center space-x-3">
              <img src={logoImg} alt="Phoenix Guardian" className="h-16 w-16 object-contain" />
              <span className="font-bold text-2xl text-primary-700">Phoenix Guardian</span>
            </Link>
            <Link to="/login" className="btn-primary">
              Sign In
            </Link>
          </div>
        </div>
      </header>
    );
  }
  
  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-20">
          {/* Logo — links to role-appropriate home */}
          <Link to={user?.role === 'admin' ? '/admin' : '/dashboard'} className="flex items-center space-x-3">
            <img src={logoImg} alt="Phoenix Guardian" className="h-16 w-16 object-contain" />
            <span className="font-bold text-2xl text-primary-700">Phoenix Guardian</span>
          </Link>
          
          {/* Navigation — role-based */}
          <nav className="hidden md:flex items-center space-x-6">
            {user?.role === 'admin' ? (
              <>
                <Link to="/admin" className="text-gray-600 hover:text-primary-600 font-medium transition-colors">
                  Home
                </Link>
                <Link to="/admin/security" className="text-red-600 hover:text-red-500 font-medium transition-colors">
                  🛡️ Security
                </Link>
                <Link to="/admin/reports" className="text-gray-600 hover:text-primary-600 font-medium transition-colors">
                  Reports
                </Link>
                <Link to="/admin/users" className="text-gray-600 hover:text-primary-600 font-medium transition-colors">
                  Users
                </Link>
                <Link to="/admin/audit-logs" className="text-gray-600 hover:text-primary-600 font-medium transition-colors">
                  Audit Logs
                </Link>
              </>
            ) : (
              <>
                <Link to="/v5-dashboard" className="text-emerald-600 hover:text-emerald-500 font-bold transition-colors flex items-center gap-1">
                  🛡️ V5 Dashboard
                </Link>

                <Link to="/dashboard" className="text-gray-600 hover:text-primary-600 font-medium transition-colors">
                  Legacy
                </Link>

                {canCreateEncounters() && (
                  <Link to="/encounters/new" className="text-gray-600 hover:text-primary-600 font-medium transition-colors">
                    New Encounter
                  </Link>
                )}

                <Link to="/treatment-shadow" className="text-purple-600 hover:text-purple-500 font-medium transition-colors flex items-center gap-1">
                  🟣 Shadow
                  <span className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" />
                </Link>

                <Link to="/silent-voice" className="text-blue-600 hover:text-blue-500 font-medium transition-colors flex items-center gap-1">
                  🔵 Voice
                  <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                </Link>

                <Link to="/zebra-hunter" className="text-amber-600 hover:text-amber-500 font-medium transition-colors flex items-center gap-1">
                  🦓 Zebra
                  <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                </Link>
              </>
            )}
          </nav>
          
          {/* User menu */}
          <div className="flex items-center space-x-4">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-gray-900">{getFullName()}</p>
              <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
            </div>
            
            <button
              onClick={handleLogout}
              className="text-gray-500 hover:text-gray-700 p-2 rounded-md hover:bg-gray-100 transition-colors"
              title="Sign out"
            >
              <svg
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
