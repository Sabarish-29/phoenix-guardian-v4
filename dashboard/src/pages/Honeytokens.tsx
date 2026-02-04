import { useEffect, useState } from 'react';
import {
  PlusIcon,
  FunnelIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { useAppDispatch, useAppSelector } from '../hooks/useStore';
import {
  fetchHoneytokens,
  fetchHoneytokenTriggers,
  selectAllHoneytokens,
  selectHoneytokenTriggers,
  selectHoneytokensLoading,
  selectHoneytokensStats,
} from '../store/slices/honeytokensSlice';
import HoneytokenCard from '../components/honeytokens/HoneytokenCard';
import TriggerTimeline from '../components/honeytokens/TriggerTimeline';
import CreateHoneytokenModal from '../components/honeytokens/CreateHoneytokenModal';
import type { HoneytokenType } from '../types/honeytoken';
import clsx from 'clsx';

/**
 * Honeytokens - Monitor and manage decoy data
 */
export default function Honeytokens() {
  const dispatch = useAppDispatch();
  const honeytokens = useAppSelector(selectAllHoneytokens);
  const triggers = useAppSelector(selectHoneytokenTriggers);
  const loading = useAppSelector(selectHoneytokensLoading);
  const stats = useAppSelector(selectHoneytokensStats);
  
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [typeFilter, setTypeFilter] = useState<HoneytokenType | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'triggered'>('all');

  useEffect(() => {
    dispatch(fetchHoneytokens());
    dispatch(fetchHoneytokenTriggers(undefined));
  }, [dispatch]);

  const filteredHoneytokens = honeytokens.filter((h) => {
    if (typeFilter !== 'all' && h.type !== typeFilter) return false;
    if (statusFilter === 'active' && h.status !== 'active') return false;
    if (statusFilter === 'triggered' && h.triggerCount === 0) return false;
    return true;
  });

  const honeytokenTypes: { value: HoneytokenType | 'all'; label: string }[] = [
    { value: 'all', label: 'All Types' },
    { value: 'patient_record', label: 'Patient Records' },
    { value: 'medication', label: 'Medications' },
    { value: 'admin_credential', label: 'Admin Credentials' },
    { value: 'api_key', label: 'API Keys' },
    { value: 'database', label: 'Databases' },
  ];

  return (
    <div className="space-y-6">
      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <p className="text-dashboard-muted text-sm">Total Honeytokens</p>
          <p className="text-2xl font-bold text-white mt-1">{stats.total}</p>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <p className="text-dashboard-muted text-sm">Active</p>
          <p className="text-2xl font-bold text-green-400 mt-1">{stats.active}</p>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <p className="text-dashboard-muted text-sm">Triggered</p>
          <p className="text-2xl font-bold text-red-400 mt-1">{stats.triggered}</p>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <p className="text-dashboard-muted text-sm">Recent Triggers</p>
          <p className="text-2xl font-bold text-orange-400 mt-1">{triggers.length}</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Honeytoken List */}
        <div className="lg:col-span-2 space-y-4">
          {/* Filters */}
          <div className="flex flex-col md:flex-row gap-4">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as HoneytokenType | 'all')}
              className="px-4 py-2 bg-dashboard-card border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
            >
              {honeytokenTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              {(['all', 'active', 'triggered'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={clsx(
                    'px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize',
                    statusFilter === status
                      ? 'bg-phoenix-500/20 text-phoenix-400 border border-phoenix-500'
                      : 'bg-dashboard-card border border-dashboard-border text-dashboard-muted hover:text-white'
                  )}
                >
                  {status}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="ml-auto flex items-center gap-2 px-4 py-2 bg-phoenix-500 text-white rounded-lg hover:bg-phoenix-600 transition-colors"
            >
              <PlusIcon className="w-5 h-5" />
              Create Honeytoken
            </button>
          </div>

          {/* Honeytoken Grid */}
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-40 skeleton rounded-xl" />
              ))}
            </div>
          ) : filteredHoneytokens.length === 0 ? (
            <div className="text-center py-12 bg-dashboard-card rounded-xl border border-dashboard-border">
              <ExclamationTriangleIcon className="w-12 h-12 mx-auto text-dashboard-muted mb-4" />
              <p className="text-dashboard-muted">No honeytokens match your filters</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredHoneytokens.map((honeytoken) => (
                <HoneytokenCard key={honeytoken.id} honeytoken={honeytoken} />
              ))}
            </div>
          )}
        </div>

        {/* Trigger Timeline */}
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Recent Triggers</h3>
          <TriggerTimeline triggers={triggers} />
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateHoneytokenModal onClose={() => setShowCreateModal(false)} />
      )}
    </div>
  );
}
