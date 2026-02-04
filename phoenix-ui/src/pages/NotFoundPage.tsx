/**
 * Not found (404) page component.
 */

import React from 'react';
import { Link } from 'react-router-dom';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center">
        <div className="text-6xl mb-4">🔍</div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Page Not Found</h1>
        <p className="text-gray-500 mb-6 max-w-md">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Link to="/dashboard" className="btn-primary">
          Return to Dashboard
        </Link>
      </div>
    </div>
  );
};

export default NotFoundPage;
