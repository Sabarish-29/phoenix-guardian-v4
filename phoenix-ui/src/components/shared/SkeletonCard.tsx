/**
 * Reusable skeleton loader card component.
 * Shows animated placeholder while API data loads.
 */

import React from 'react';

interface SkeletonCardProps {
  lines?: number;
  className?: string;
}

export const SkeletonCard: React.FC<SkeletonCardProps> = ({ lines = 3, className = '' }) => (
  <div className={`animate-pulse bg-gray-800 rounded-xl p-4 ${className}`}>
    <div className="h-4 bg-gray-700 rounded w-3/4 mb-3" />
    {Array.from({ length: lines }).map((_, i) => (
      <div
        key={i}
        className={`h-3 bg-gray-700 rounded mb-2 ${
          i === lines - 1 ? 'w-1/2' : 'w-full'
        }`}
      />
    ))}
  </div>
);

interface SkeletonRowProps {
  count?: number;
}

export const SkeletonRow: React.FC<SkeletonRowProps> = ({ count = 3 }) => (
  <div className="space-y-3">
    {Array.from({ length: count }).map((_, i) => (
      <div key={i} className="animate-pulse flex items-center space-x-3 bg-gray-800/50 rounded-lg p-3">
        <div className="h-3 w-3 rounded-full bg-gray-700" />
        <div className="flex-1">
          <div className="h-3 bg-gray-700 rounded w-2/3 mb-1" />
          <div className="h-2 bg-gray-700 rounded w-1/2" />
        </div>
        <div className="h-6 w-16 bg-gray-700 rounded" />
      </div>
    ))}
  </div>
);

export const DashboardSkeleton: React.FC = () => (
  <div className="space-y-6 animate-pulse">
    {/* Header skeleton */}
    <div className="bg-gray-800 rounded-xl p-6">
      <div className="h-6 bg-gray-700 rounded w-1/3 mb-2" />
      <div className="h-4 bg-gray-700 rounded w-1/2 mb-4" />
      <div className="flex gap-4">
        <div className="h-3 bg-gray-700 rounded w-32" />
        <div className="h-3 bg-gray-700 rounded w-32" />
        <div className="h-3 bg-gray-700 rounded w-32" />
      </div>
    </div>

    {/* Alert rows skeleton */}
    <div className="bg-gray-800 rounded-xl p-6">
      <div className="h-5 bg-gray-700 rounded w-1/4 mb-4" />
      <SkeletonRow count={3} />
    </div>

    {/* Agent cards skeleton */}
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <SkeletonCard lines={5} />
      <SkeletonCard lines={5} />
      <SkeletonCard lines={5} />
    </div>
  </div>
);

export default SkeletonCard;
