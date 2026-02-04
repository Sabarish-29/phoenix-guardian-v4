import { useEffect, useState } from 'react';
import {
  PlusIcon,
  FunnelIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { useAppDispatch, useAppSelector } from '../hooks/useStore';
import {
  fetchIncidents,
  selectAllIncidents,
  selectIncidentsLoading,
  selectIncidentsStats,
} from '../store/slices/incidentsSlice';
import IncidentCard from '../components/incidents/IncidentCard';
import IncidentDetailModal from '../components/incidents/IncidentDetailModal';
import CreateIncidentModal from '../components/incidents/CreateIncidentModal';
import IncidentKanban from '../components/incidents/IncidentKanban';
import type { Incident, IncidentStatus, IncidentPriority } from '../types/incident';
import clsx from 'clsx';

type ViewMode = 'list' | 'kanban';

/**
 * Incidents - Incident response workflow management
 */
export default function Incidents() {
  const dispatch = useAppDispatch();
  const incidents = useAppSelector(selectAllIncidents);
  const loading = useAppSelector(selectIncidentsLoading);
  const stats = useAppSelector(selectIncidentsStats);
  
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<IncidentPriority | 'all'>('all');

  useEffect(() => {
    dispatch(fetchIncidents(undefined));
  }, [dispatch]);

  const filteredIncidents = incidents.filter((incident) => {
    if (statusFilter !== 'all' && incident.status !== statusFilter) return false;
    if (priorityFilter !== 'all' && incident.priority !== priorityFilter) return false;
    return true;
  });

  const statusOptions: { value: IncidentStatus | 'all'; label: string; color: string }[] = [
    { value: 'all', label: 'All', color: '' },
    { value: 'open', label: 'Open', color: 'text-red-400' },
    { value: 'investigating', label: 'Investigating', color: 'text-orange-400' },
    { value: 'contained', label: 'Contained', color: 'text-yellow-400' },
    { value: 'resolved', label: 'Resolved', color: 'text-green-400' },
  ];

  return (
    <div className="space-y-6">
      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <p className="text-dashboard-muted text-sm">Total</p>
          <p className="text-2xl font-bold text-white mt-1">{stats.total}</p>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-red-500/30 p-4">
          <p className="text-dashboard-muted text-sm">Open</p>
          <p className="text-2xl font-bold text-red-400 mt-1">{stats.open}</p>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-orange-500/30 p-4">
          <p className="text-dashboard-muted text-sm">Investigating</p>
          <p className="text-2xl font-bold text-orange-400 mt-1">{stats.investigating}</p>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-yellow-500/30 p-4">
          <p className="text-dashboard-muted text-sm">Contained</p>
          <p className="text-2xl font-bold text-yellow-400 mt-1">{stats.contained}</p>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-green-500/30 p-4">
          <p className="text-dashboard-muted text-sm">Resolved</p>
          <p className="text-2xl font-bold text-green-400 mt-1">{stats.resolved}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* Status Filter */}
        <div className="flex gap-2 overflow-x-auto pb-2 md:pb-0">
          {statusOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => setStatusFilter(option.value)}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap',
                statusFilter === option.value
                  ? 'bg-phoenix-500/20 text-phoenix-400 border border-phoenix-500'
                  : 'bg-dashboard-card border border-dashboard-border text-dashboard-muted hover:text-white'
              )}
            >
              {option.label}
            </button>
          ))}
        </div>

        {/* Priority Filter */}
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value as IncidentPriority | 'all')}
          className="px-4 py-2 bg-dashboard-card border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
        >
          <option value="all">All Priorities</option>
          <option value="P1">P1 - Critical</option>
          <option value="P2">P2 - High</option>
          <option value="P3">P3 - Medium</option>
          <option value="P4">P4 - Low</option>
        </select>

        {/* View Toggle */}
        <div className="flex gap-1 bg-dashboard-card border border-dashboard-border rounded-lg p-1">
          <button
            onClick={() => setViewMode('list')}
            className={clsx(
              'px-3 py-1 rounded text-sm transition-colors',
              viewMode === 'list' ? 'bg-phoenix-500 text-white' : 'text-dashboard-muted hover:text-white'
            )}
          >
            List
          </button>
          <button
            onClick={() => setViewMode('kanban')}
            className={clsx(
              'px-3 py-1 rounded text-sm transition-colors',
              viewMode === 'kanban' ? 'bg-phoenix-500 text-white' : 'text-dashboard-muted hover:text-white'
            )}
          >
            Kanban
          </button>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="ml-auto flex items-center gap-2 px-4 py-2 bg-phoenix-500 text-white rounded-lg hover:bg-phoenix-600 transition-colors"
        >
          <PlusIcon className="w-5 h-5" />
          New Incident
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-32 skeleton rounded-xl" />
          ))}
        </div>
      ) : viewMode === 'kanban' ? (
        <IncidentKanban
          incidents={incidents}
          onSelectIncident={setSelectedIncident}
        />
      ) : filteredIncidents.length === 0 ? (
        <div className="text-center py-12 bg-dashboard-card rounded-xl border border-dashboard-border">
          <ExclamationTriangleIcon className="w-12 h-12 mx-auto text-dashboard-muted mb-4" />
          <p className="text-dashboard-muted">No incidents match your filters</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredIncidents.map((incident) => (
            <IncidentCard
              key={incident.id}
              incident={incident}
              onClick={() => setSelectedIncident(incident)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showCreateModal && (
        <CreateIncidentModal onClose={() => setShowCreateModal(false)} />
      )}
      {selectedIncident && (
        <IncidentDetailModal
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
        />
      )}
    </div>
  );
}
