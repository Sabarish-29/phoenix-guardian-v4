/**
 * Loading spinner component.
 */

import React from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  message?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  className = '',
  message,
}) => {
  const sizeClasses = {
    sm: 'h-4 w-4 border-2',
    md: 'h-8 w-8 border-2',
    lg: 'h-12 w-12 border-3',
  };
  
  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <div
        className={`animate-spin rounded-full border-primary-600 border-t-transparent ${sizeClasses[size]}`}
        role="status"
        aria-label="Loading"
      />
      {message && <p className="mt-2 text-sm text-gray-600">{message}</p>}
    </div>
  );
};

/**
 * Full-page loading screen
 */
export const LoadingScreen: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <LoadingSpinner size="lg" />
        <p className="mt-4 text-gray-600">{message}</p>
      </div>
    </div>
  );
};

export default LoadingSpinner;
