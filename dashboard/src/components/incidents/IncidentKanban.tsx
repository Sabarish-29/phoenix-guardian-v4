import type { Incident, IncidentStatus } from '../../types/incident';
import IncidentCard from './IncidentCard';
import clsx from 'clsx';

interface IncidentKanbanProps {
  incidents: Incident[];
  onSelectIncident: (incident: Incident) => void;
}

const columns: { status: IncidentStatus; label: string; color: string }[] = [
  { status: 'open', label: 'Open', color: 'border-red-500' },
  { status: 'investigating', label: 'Investigating', color: 'border-orange-500' },
  { status: 'contained', label: 'Contained', color: 'border-yellow-500' },
  { status: 'resolved', label: 'Resolved', color: 'border-green-500' },
];

/**
 * Kanban board view for incidents
 */
export default function IncidentKanban({ incidents, onSelectIncident }: IncidentKanbanProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 overflow-x-auto">
      {columns.map((column) => {
        const columnIncidents = incidents.filter(i => i.status === column.status);
        
        return (
          <div
            key={column.status}
            className={clsx(
              'bg-dashboard-card rounded-xl border-t-4 min-h-[400px]',
              column.color
            )}
          >
            <div className="p-3 border-b border-dashboard-border">
              <div className="flex items-center justify-between">
                <h3 className="text-white font-medium">{column.label}</h3>
                <span className="text-dashboard-muted text-sm">{columnIncidents.length}</span>
              </div>
            </div>
            <div className="p-2 space-y-2 max-h-[600px] overflow-y-auto">
              {columnIncidents.map((incident) => (
                <div
                  key={incident.id}
                  onClick={() => onSelectIncident(incident)}
                  className="p-3 bg-dashboard-bg rounded-lg cursor-pointer hover:bg-dashboard-border transition-colors"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={clsx(
                      'px-1.5 py-0.5 rounded text-xs font-bold',
                      incident.priority === 'P1' ? 'bg-red-400/20 text-red-400' :
                      incident.priority === 'P2' ? 'bg-orange-400/20 text-orange-400' :
                      incident.priority === 'P3' ? 'bg-yellow-400/20 text-yellow-400' :
                      'bg-green-400/20 text-green-400'
                    )}>
                      {incident.priority}
                    </span>
                    <span className="text-xs text-dashboard-muted truncate">
                      {incident.category.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <p className="text-white text-sm font-medium line-clamp-2">
                    {incident.title}
                  </p>
                  {incident.assignee && (
                    <p className="text-xs text-dashboard-muted mt-2">
                      {incident.assignee.name}
                    </p>
                  )}
                </div>
              ))}
              {columnIncidents.length === 0 && (
                <p className="text-center text-dashboard-muted text-sm py-8">
                  No incidents
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
