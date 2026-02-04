import { XMarkIcon } from '@heroicons/react/24/outline';
import type { ThreatFilters, AttackType } from '../../types/threat';

interface ThreatFiltersPanelProps {
  filters: ThreatFilters;
  onFilterChange: (filters: Partial<ThreatFilters>) => void;
  onClose: () => void;
}

const attackTypes: { value: AttackType; label: string }[] = [
  { value: 'ransomware', label: 'Ransomware' },
  { value: 'data_exfiltration', label: 'Data Exfiltration' },
  { value: 'privilege_escalation', label: 'Privilege Escalation' },
  { value: 'lateral_movement', label: 'Lateral Movement' },
  { value: 'credential_theft', label: 'Credential Theft' },
  { value: 'phishing', label: 'Phishing' },
  { value: 'malware', label: 'Malware' },
  { value: 'unauthorized_access', label: 'Unauthorized Access' },
  { value: 'ddos', label: 'DDoS' },
  { value: 'insider_threat', label: 'Insider Threat' },
];

const timeRanges = [
  { value: '1h', label: 'Last Hour' },
  { value: '6h', label: 'Last 6 Hours' },
  { value: '24h', label: 'Last 24 Hours' },
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
];

/**
 * Expanded filters panel for threat feed
 */
export default function ThreatFiltersPanel({ filters, onFilterChange, onClose }: ThreatFiltersPanelProps) {
  const toggleAttackType = (type: AttackType) => {
    const newTypes = filters.attackType.includes(type)
      ? filters.attackType.filter(t => t !== type)
      : [...filters.attackType, type];
    onFilterChange({ attackType: newTypes });
  };

  return (
    <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold">Advanced Filters</h3>
        <button onClick={onClose} className="text-dashboard-muted hover:text-white">
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Time Range */}
        <div>
          <label className="block text-sm text-dashboard-muted mb-2">Time Range</label>
          <select
            value={filters.timeRange}
            onChange={(e) => onFilterChange({ timeRange: e.target.value as any })}
            className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
          >
            {timeRanges.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>
        </div>

        {/* Acknowledged */}
        <div>
          <label className="block text-sm text-dashboard-muted mb-2">Status</label>
          <select
            value={filters.acknowledged === undefined ? 'all' : filters.acknowledged ? 'ack' : 'unack'}
            onChange={(e) => {
              const value = e.target.value;
              onFilterChange({
                acknowledged: value === 'all' ? undefined : value === 'ack'
              });
            }}
            className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
          >
            <option value="all">All</option>
            <option value="unack">Unacknowledged</option>
            <option value="ack">Acknowledged</option>
          </select>
        </div>
      </div>

      {/* Attack Types */}
      <div className="mt-4">
        <label className="block text-sm text-dashboard-muted mb-2">Attack Types</label>
        <div className="flex flex-wrap gap-2">
          {attackTypes.map((type) => (
            <button
              key={type.value}
              onClick={() => toggleAttackType(type.value)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filters.attackType.includes(type.value)
                  ? 'bg-phoenix-500 text-white'
                  : 'bg-dashboard-border text-dashboard-muted hover:text-white'
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
