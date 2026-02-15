/**
 * Encounters list page component.
 * 
 * Shows a paginated list of all encounters with filtering options.
 */

import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { encounterService } from '../api/services/encounterService';
import type { EncounterStatus } from '../api/services/encounterService';
import { useAuthStore } from '../stores/authStore';
import { LoadingSpinner } from '../components/LoadingSpinner';

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

const STATUS_OPTIONS: { value: EncounterStatus | ''; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'awaiting_review', label: 'Awaiting Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'signed', label: 'Signed' },
];

export const EncountersListPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { canCreateEncounters, canSignNotes } = useAuthStore();
  
  // Get filters from URL
  const page = parseInt(searchParams.get('page') || '1', 10);
  const statusFilter = (searchParams.get('status') || '') as EncounterStatus | '';
  const searchQuery = searchParams.get('search') || '';
  
  // Local search state
  const [localSearch, setLocalSearch] = useState(searchQuery);
  
  // Fetch encounters
  const { data, isLoading, error } = useQuery({
    queryKey: ['encounters', 'list', page, statusFilter, searchQuery],
    queryFn: () => encounterService.listEncounters({
      page,
      page_size: 10,
      status: statusFilter || undefined,
      search: searchQuery || undefined,
    }),
  });
  
  const updateFilters = (updates: Record<string, string>) => {
    const newParams = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) {
        newParams.set(key, value);
      } else {
        newParams.delete(key);
      }
    });
    // Reset to page 1 when filters change (except when just changing page)
    if (!('page' in updates)) {
      newParams.set('page', '1');
    }
    setSearchParams(newParams);
  };
  
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    updateFilters({ search: localSearch });
  };
  
  const encounters = data?.items || [];
  const totalPages = data?.pages || 1;
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Encounters</h1>
          <p className="text-gray-500">
            {data?.total || 0} total encounters
          </p>
        </div>
        
        {canCreateEncounters() && (
          <Link to="/encounters/new" className="btn-primary">
            + New Encounter
          </Link>
        )}
      </div>
      
      {/* Filters */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex-1">
            <div className="relative">
              <input
                type="text"
                value={localSearch}
                onChange={(e) => setLocalSearch(e.target.value)}
                placeholder="Search by patient name or MRN..."
                className="input-field pl-10"
              />
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
          </form>
          
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => updateFilters({ status: e.target.value })}
            className="input-field w-full md:w-48"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      
      {/* Encounters Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="py-12">
            <LoadingSpinner size="lg" className="mx-auto" />
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-500">Failed to load encounters. Please try again.</p>
          </div>
        ) : encounters.length === 0 ? (
          <div className="text-center py-12">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="mt-2 text-gray-500">No encounters found.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Patient
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Chief Complaint
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {encounters.map((encounter) => (
                  <tr key={encounter.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <p className="font-medium text-gray-900">
                          {encounter.patientFirstName} {encounter.patientLastName}
                        </p>
                        {encounter.patientMrn && (
                          <p className="text-sm text-gray-500">MRN: {encounter.patientMrn}</p>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 capitalize">
                      {encounter.encounterType?.replace(/_/g, ' ') || 'N/A'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                      {encounter.chiefComplaint || 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={encounter.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(encounter.createdAt).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                      <Link
                        to={
                          encounter.status === 'awaiting_review' && canSignNotes()
                            ? `/encounters/${encounter.uuid}/review`
                            : `/encounters/${encounter.uuid}`
                        }
                        className="text-primary-600 hover:text-primary-700 font-medium"
                      >
                        {encounter.status === 'awaiting_review' && canSignNotes()
                          ? 'Review'
                          : 'View'}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        
        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Page {page} of {totalPages}
            </p>
            <div className="flex space-x-2">
              <button
                onClick={() => updateFilters({ page: String(page - 1) })}
                disabled={page <= 1}
                className="btn-secondary text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => updateFilters({ page: String(page + 1) })}
                disabled={page >= totalPages}
                className="btn-secondary text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EncountersListPage;
