import { useAppSelector } from '../../hooks/useStore';
import { selectOpenIncidents } from '../../store/slices/incidentsSlice';
import { format } from 'date-fns';
import clsx from 'clsx';

const priorityColors = {
  P1: 'text-red-400 bg-red-400/20',
  P2: 'text-orange-400 bg-orange-400/20',
  P3: 'text-yellow-400 bg-yellow-400/20',
  P4: 'text-green-400 bg-green-400/20',
};

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
 * List of active incidents for dashboard
 */
export default function ActiveIncidents() {
  const incidents = useAppSelector(selectOpenIncidents);

  if (incidents.length === 0) {
    return (
      <div className="text-center py-8 text-dashboard-muted">
        No active incidents
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {incidents.slice(0, 5).map((incident) => (
        <div
          key={incident.id}
          className="flex items-start gap-3 p-3 rounded-lg bg-dashboard-bg/50 hover:bg-dashboard-bg transition-colors cursor-pointer"
        >
          <span className={clsx(
            'px-2 py-0.5 rounded text-xs font-bold',
            priorityColors[incident.priority]
          )}>
            {incident.priority}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-white font-medium truncate">{incident.title}</p>
            <div className="flex items-center gap-2 mt-1 text-xs">
              <span className={clsx('capitalize', statusColors[incident.status])}>
                {incident.status}
              </span>
              <span className="text-dashboard-muted">•</span>
              <span className="text-dashboard-muted">
                {format(new Date(incident.createdAt), 'MMM d, HH:mm')}
              </span>
            </div>
          </div>
          {incident.assignee && (
            <span className="text-xs text-dashboard-muted">
              {incident.assignee.name}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
