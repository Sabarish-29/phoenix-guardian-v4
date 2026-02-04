import { XMarkIcon } from '@heroicons/react/24/outline';
import { format } from 'date-fns';
import type { Incident } from '../../types/incident';
import clsx from 'clsx';

interface IncidentDetailModalProps {
  incident: Incident;
  onClose: () => void;
}

const statusColors = {
  open: 'text-red-400',
  investigating: 'text-orange-400',
  contained: 'text-yellow-400',
  eradicating: 'text-blue-400',
  recovering: 'text-purple-400',
  resolved: 'text-green-400',
  closed: 'text-gray-400',
};

/**
 * Modal for viewing incident details
 */
export default function IncidentDetailModal({ incident, onClose }: IncidentDetailModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-dashboard-card rounded-xl border border-dashboard-border w-full max-w-2xl max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-dashboard-border">
          <div className="flex items-center gap-3">
            <span className={clsx(
              'px-2 py-1 rounded text-xs font-bold',
              incident.priority === 'P1' ? 'bg-red-400/20 text-red-400' :
              incident.priority === 'P2' ? 'bg-orange-400/20 text-orange-400' :
              incident.priority === 'P3' ? 'bg-yellow-400/20 text-yellow-400' :
              'bg-green-400/20 text-green-400'
            )}>
              {incident.priority}
            </span>
            <h2 className="text-lg font-semibold text-white">{incident.title}</h2>
          </div>
          <button onClick={onClose} className="text-dashboard-muted hover:text-white">
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <div className="p-4 overflow-y-auto max-h-[60vh]">
          <p className="text-dashboard-text mb-6">{incident.description}</p>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <label className="text-sm text-dashboard-muted">Status</label>
              <p className={clsx('capitalize font-medium', statusColors[incident.status])}>
                {incident.status}
              </p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Category</label>
              <p className="text-white capitalize">{incident.category.replace(/_/g, ' ')}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Created</label>
              <p className="text-white">{format(new Date(incident.createdAt), 'PPpp')}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Assignee</label>
              <p className="text-white">{incident.assignee?.name || 'Unassigned'}</p>
            </div>
          </div>

          {/* Affected Assets */}
          {incident.affectedAssets.length > 0 && (
            <div className="mb-6">
              <label className="text-sm text-dashboard-muted block mb-2">Affected Assets</label>
              <div className="flex flex-wrap gap-2">
                {incident.affectedAssets.map((asset, idx) => (
                  <span key={idx} className="px-2 py-1 bg-dashboard-border rounded text-sm text-white">
                    {asset}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Containment Actions */}
          {incident.containmentActions.length > 0 && (
            <div className="mb-6">
              <label className="text-sm text-dashboard-muted block mb-2">Containment Actions</label>
              <ul className="space-y-1">
                {incident.containmentActions.map((action, idx) => (
                  <li key={idx} className="text-dashboard-text text-sm flex items-start gap-2">
                    <span className="text-green-400">✓</span>
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-dashboard-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-dashboard-muted hover:text-white transition-colors"
          >
            Close
          </button>
          <button className="px-4 py-2 bg-phoenix-500 text-white rounded-lg hover:bg-phoenix-600 transition-colors">
            Update Status
          </button>
        </div>
      </div>
    </div>
  );
}
