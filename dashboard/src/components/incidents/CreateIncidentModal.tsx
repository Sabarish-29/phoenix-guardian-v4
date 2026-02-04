import { useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { useAppDispatch } from '../../hooks/useStore';
import { createIncident } from '../../store/slices/incidentsSlice';
import type { IncidentPriority, IncidentCategory } from '../../types/incident';

interface CreateIncidentModalProps {
  onClose: () => void;
}

/**
 * Modal for creating a new incident
 */
export default function CreateIncidentModal({ onClose }: CreateIncidentModalProps) {
  const dispatch = useAppDispatch();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<IncidentPriority>('P2');
  const [category, setCategory] = useState<IncidentCategory>('unauthorized_access');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await dispatch(createIncident({
        title,
        description,
        priority,
        category,
        status: 'open',
        severity: priority === 'P1' ? 'critical' : priority === 'P2' ? 'high' : 'medium',
        affectedAssets: [],
        affectedDepartments: [],
        threatIds: [],
        slaBreach: false,
        containmentActions: [],
        remediationActions: [],
      }));
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-dashboard-card rounded-xl border border-dashboard-border w-full max-w-lg">
        <div className="flex items-center justify-between p-4 border-b border-dashboard-border">
          <h2 className="text-lg font-semibold text-white">Create Incident</h2>
          <button onClick={onClose} className="text-dashboard-muted hover:text-white">
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm text-dashboard-muted mb-1">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
              placeholder="Brief incident title"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dashboard-muted mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as IncidentPriority)}
                className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
              >
                <option value="P1">P1 - Critical</option>
                <option value="P2">P2 - High</option>
                <option value="P3">P3 - Medium</option>
                <option value="P4">P4 - Low</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-dashboard-muted mb-1">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as IncidentCategory)}
                className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
              >
                <option value="malware">Malware</option>
                <option value="ransomware">Ransomware</option>
                <option value="data_breach">Data Breach</option>
                <option value="unauthorized_access">Unauthorized Access</option>
                <option value="insider_threat">Insider Threat</option>
                <option value="phishing">Phishing</option>
                <option value="ddos">DDoS</option>
                <option value="policy_violation">Policy Violation</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-dashboard-muted mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
              placeholder="Describe the incident..."
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-dashboard-muted hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !title}
              className="px-4 py-2 bg-phoenix-500 text-white rounded-lg hover:bg-phoenix-600 transition-colors disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Incident'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
