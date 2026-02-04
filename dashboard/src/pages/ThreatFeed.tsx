import { useEffect, useState, useCallback } from 'react';
import {
  FunnelIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { useAppDispatch, useAppSelector } from '../hooks/useStore';
import {
  fetchThreats,
  selectFilteredThreats,
  selectThreatsLoading,
  selectThreatFilters,
  setFilters,
  clearFilters,
} from '../store/slices/threatsSlice';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import ThreatCard from '../components/threats/ThreatCard';
import ThreatDetailModal from '../components/threats/ThreatDetailModal';
import ThreatFiltersPanel from '../components/threats/ThreatFiltersPanel';
import type { Threat, ThreatSeverity } from '../types/threat';
import clsx from 'clsx';

/**
 * ThreatFeed - Real-time threat feed with filtering
 */
export default function ThreatFeed() {
  const dispatch = useAppDispatch();
  const threats = useAppSelector(selectFilteredThreats);
  const loading = useAppSelector(selectThreatsLoading);
  const filters = useAppSelector(selectThreatFilters);
  
  const [showFilters, setShowFilters] = useState(false);
  const [selectedThreat, setSelectedThreat] = useState<Threat | null>(null);
  const [searchInput, setSearchInput] = useState(filters.searchQuery);

  const fetchAction = useCallback(() => fetchThreats(filters), [filters]);
  const { refresh } = useAutoRefresh(fetchAction);

  useEffect(() => {
    dispatch(fetchThreats(filters));
  }, [dispatch, filters]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== filters.searchQuery) {
        dispatch(setFilters({ searchQuery: searchInput }));
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput, dispatch, filters.searchQuery]);

  const handleSeverityFilter = (severity: ThreatSeverity) => {
    const newSeverities = filters.severity.includes(severity)
      ? filters.severity.filter(s => s !== severity)
      : [...filters.severity, severity];
    dispatch(setFilters({ severity: newSeverities }));
  };

  const hasActiveFilters = filters.severity.length > 0 || 
    filters.attackType.length > 0 || 
    filters.searchQuery;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <p className="text-dashboard-muted">
            {threats.length} threats {hasActiveFilters && '(filtered)'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refresh()}
            className="p-2 text-dashboard-muted hover:text-white hover:bg-dashboard-border rounded-lg transition-colors"
            title="Refresh"
          >
            <ArrowPathIcon className={clsx('w-5 h-5', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dashboard-muted" />
          <input
            type="text"
            placeholder="Search threats..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-dashboard-card border border-dashboard-border rounded-lg text-white placeholder-dashboard-muted focus:outline-none focus:border-phoenix-500"
          />
          {searchInput && (
            <button
              onClick={() => setSearchInput('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-dashboard-muted hover:text-white"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          )}
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={clsx(
            'flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
            showFilters || hasActiveFilters
              ? 'bg-phoenix-500/20 border-phoenix-500 text-phoenix-400'
              : 'bg-dashboard-card border-dashboard-border text-dashboard-muted hover:text-white'
          )}
        >
          <FunnelIcon className="w-5 h-5" />
          <span>Filters</span>
          {hasActiveFilters && (
            <span className="bg-phoenix-500 text-white text-xs px-1.5 py-0.5 rounded-full">
              {filters.severity.length + filters.attackType.length}
            </span>
          )}
        </button>
      </div>

      {/* Quick Severity Filters */}
      <div className="flex flex-wrap gap-2">
        {(['critical', 'high', 'medium', 'low'] as ThreatSeverity[]).map((severity) => (
          <button
            key={severity}
            onClick={() => handleSeverityFilter(severity)}
            className={clsx(
              'px-3 py-1 rounded-full text-sm font-medium transition-colors capitalize',
              filters.severity.includes(severity)
                ? severity === 'critical' ? 'bg-threat-critical text-white'
                : severity === 'high' ? 'bg-threat-high text-white'
                : severity === 'medium' ? 'bg-threat-medium text-black'
                : 'bg-threat-low text-white'
                : 'bg-dashboard-border text-dashboard-muted hover:text-white'
            )}
          >
            {severity}
          </button>
        ))}
        {hasActiveFilters && (
          <button
            onClick={() => {
              dispatch(clearFilters());
              setSearchInput('');
            }}
            className="px-3 py-1 text-sm text-dashboard-muted hover:text-white"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <ThreatFiltersPanel
          filters={filters}
          onFilterChange={(newFilters) => dispatch(setFilters(newFilters))}
          onClose={() => setShowFilters(false)}
        />
      )}

      {/* Threat List */}
      <div className="space-y-3">
        {loading && threats.length === 0 ? (
          // Loading skeleton
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-24 skeleton rounded-xl" />
          ))
        ) : threats.length === 0 ? (
          <div className="text-center py-12 text-dashboard-muted">
            <ShieldExclamationIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No threats match your filters</p>
          </div>
        ) : (
          threats.map((threat) => (
            <ThreatCard
              key={threat.id}
              threat={threat}
              onClick={() => setSelectedThreat(threat)}
            />
          ))
        )}
      </div>

      {/* Detail Modal */}
      {selectedThreat && (
        <ThreatDetailModal
          threat={selectedThreat}
          onClose={() => setSelectedThreat(null)}
        />
      )}
    </div>
  );
}

// Import at top since it's used in empty state
import { ShieldExclamationIcon } from '@heroicons/react/24/outline';
