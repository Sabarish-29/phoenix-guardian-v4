/**
 * Dashboard page component.
 * 
 * Main landing page after login showing:
 * - Summary statistics
 * - Recent encounters
 * - Quick actions
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { encounterService } from '../api/services/encounterService';
import { useAuthStore } from '../stores/authStore';
import { LoadingSpinner } from '../components/LoadingSpinner';
import type { EncounterStatus } from '../api/services/encounterService';

/**
 * Status badge component
 */
const StatusBadge: React.FC<{ status: EncounterStatus }> = ({ status }) => {
  const statusConfig: Record<EncounterStatus, { label: string; className: string }> = {
    pending: { label: 'Pending', className: 'bg-gray-100 text-gray-700' },
    processing: { label: 'Processing', className: 'bg-blue-100 text-blue-700' },
    transcription_complete: { label: 'Transcribed', className: 'bg-purple-100 text-purple-700' },
    scribe_processing: { label: 'AI Processing', className: 'bg-indigo-100 text-indigo-700' },
    awaiting_review: { label: 'Awaiting Review', className: 'bg-amber-100 text-amber-700' },
    approved: { label: 'Approved', className: 'bg-green-100 text-green-700' },
    rejected: { label: 'Rejected', className: 'bg-red-100 text-red-700' },
    signed: { label: 'Signed', className: 'bg-emerald-100 text-emerald-700' },
    error: { label: 'Error', className: 'bg-red-100 text-red-700' },
  };
  
  const config = statusConfig[status] || { label: status, className: 'bg-gray-100 text-gray-700' };
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  );
};

/**
 * Stat card component
 */
const StatCard: React.FC<{
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
}> = ({ title, value, icon, color }) => (
  <div className="card">
    <div className="flex items-center">
      <div className={`p-3 rounded-lg ${color}`}>{icon}</div>
      <div className="ml-4">
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
      </div>
    </div>
  </div>
);

export const DashboardPage: React.FC = () => {
  const { user, canCreateEncounters, canSignNotes } = useAuthStore();
  
  // Fetch recent encounters
  const { data: encountersData, isLoading: isLoadingEncounters } = useQuery({
    queryKey: ['encounters', 'recent'],
    queryFn: () => encounterService.listEncounters({ page: 1, page_size: 5 }),
  });
  
  // Fetch encounters awaiting review
  const { data: awaitingReviewData, isLoading: isLoadingAwaiting } = useQuery({
    queryKey: ['encounters', 'awaiting-review'],
    queryFn: () => encounterService.getAwaitingReview(1, 10),
    enabled: canSignNotes(),
  });
  
  const recentEncounters = encountersData?.items || [];
  const awaitingReview = awaitingReviewData?.items || [];
  const awaitingCount = awaitingReviewData?.total || 0;
  
  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {user?.firstName}!
          </h1>
          <p className="mt-1 text-gray-500">
            Here's what's happening with your encounters today.
          </p>
        </div>
        
        {canCreateEncounters() && (
          <Link to="/encounters/new" className="mt-4 sm:mt-0 btn-primary">
            + New Encounter
          </Link>
        )}
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Encounters"
          value={encountersData?.total || 0}
          icon={
            <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          }
          color="bg-primary-500"
        />
        
        {canSignNotes() && (
          <StatCard
            title="Awaiting Review"
            value={awaitingCount}
            icon={
              <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            color="bg-amber-500"
          />
        )}
        
        <StatCard
          title="Approved Today"
          value={0}
          icon={
            <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          color="bg-green-500"
        />
        
        <StatCard
          title="Processing"
          value={0}
          icon={
            <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          }
          color="bg-blue-500"
        />
      </div>
      
      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Awaiting Review Section */}
        {canSignNotes() && (
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Awaiting Your Review</h2>
              {awaitingCount > 5 && (
                <Link to="/encounters?status=awaiting_review" className="text-sm text-primary-600 hover:text-primary-700">
                  View all ({awaitingCount})
                </Link>
              )}
            </div>
            
            {isLoadingAwaiting ? (
              <div className="py-8">
                <LoadingSpinner size="md" className="mx-auto" />
              </div>
            ) : awaitingReview.length === 0 ? (
              <div className="text-center py-8">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="mt-2 text-gray-500">All caught up! No encounters awaiting review.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {awaitingReview.slice(0, 5).map((encounter) => (
                  <Link
                    key={encounter.id}
                    to={`/encounters/${encounter.uuid}/review`}
                    className="block p-3 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-900">
                          {encounter.patientFirstName} {encounter.patientLastName}
                        </p>
                        <p className="text-sm text-gray-500">
                          {encounter.chiefComplaint || 'No chief complaint'}
                        </p>
                      </div>
                      <StatusBadge status={encounter.status} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
        
        {/* Recent Encounters Section */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Encounters</h2>
            <Link to="/encounters" className="text-sm text-primary-600 hover:text-primary-700">
              View all
            </Link>
          </div>
          
          {isLoadingEncounters ? (
            <div className="py-8">
              <LoadingSpinner size="md" className="mx-auto" />
            </div>
          ) : recentEncounters.length === 0 ? (
            <div className="text-center py-8">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="mt-2 text-gray-500">No encounters yet.</p>
              {canCreateEncounters() && (
                <Link to="/encounters/new" className="mt-3 inline-block text-primary-600 hover:text-primary-700">
                  Create your first encounter →
                </Link>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {recentEncounters.map((encounter) => (
                <Link
                  key={encounter.id}
                  to={`/encounters/${encounter.uuid}`}
                  className="block p-3 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900">
                        {encounter.patientFirstName} {encounter.patientLastName}
                      </p>
                      <p className="text-sm text-gray-500">
                        {new Date(encounter.createdAt).toLocaleDateString()} · {encounter.encounterType || 'General'}
                      </p>
                    </div>
                    <StatusBadge status={encounter.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {canCreateEncounters() && (
            <Link
              to="/encounters/new"
              className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <div className="p-2 bg-primary-100 rounded-lg">
                <svg className="h-6 w-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </div>
              <span className="ml-3 font-medium text-gray-900">New Encounter</span>
            </Link>
          )}
          
          <Link
            to="/encounters"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
          >
            <div className="p-2 bg-blue-100 rounded-lg">
              <svg className="h-6 w-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span className="ml-3 font-medium text-gray-900">All Encounters</span>
          </Link>
          
          <Link
            to="/profile"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
          >
            <div className="p-2 bg-purple-100 rounded-lg">
              <svg className="h-6 w-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <span className="ml-3 font-medium text-gray-900">My Profile</span>
          </Link>
          
          <Link
            to="/help"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
          >
            <div className="p-2 bg-gray-100 rounded-lg">
              <svg className="h-6 w-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="ml-3 font-medium text-gray-900">Help & Support</span>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
