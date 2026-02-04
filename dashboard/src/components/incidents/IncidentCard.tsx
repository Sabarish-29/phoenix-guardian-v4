import { format } from 'date-fns';
import { UserCircleIcon, ClockIcon } from '@heroicons/react/24/outline';
import type { Incident } from '../../types/incident';
import clsx from 'clsx';

interface IncidentCardProps {
  incident: Incident;
  onClick: () => void;
}

const priorityColors = {
  P1: 'text-red-400 bg-red-400/20 border-red-400/30',
  P2: 'text-orange-400 bg-orange-400/20 border-orange-400/30',
  P3: 'text-yellow-400 bg-yellow-400/20 border-yellow-400/30',
  P4: 'text-green-400 bg-green-400/20 border-green-400/30',
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
 * Card for displaying an incident
 */
export default function IncidentCard({ incident, onClick }: IncidentCardProps) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        'p-4 rounded-xl border cursor-pointer transition-all hover:scale-[1.01]',
        priorityColors[incident.priority]
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={clsx(
            'px-2 py-0.5 rounded text-xs font-bold',
            priorityColors[incident.priority]
          )}>
            {incident.priority}
          </span>
          <h4 className="text-white font-medium">{incident.title}</h4>
        </div>
        <span className={clsx('text-sm capitalize', statusColors[incident.status])}>
          {incident.status}
        </span>
      </div>

      <p className="text-sm text-dashboard-muted mb-3 line-clamp-2">
        {incident.description}
      </p>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-4">
          <span className="px-2 py-0.5 bg-dashboard-border rounded text-xs capitalize text-dashboard-muted">
            {incident.category.replace(/_/g, ' ')}
          </span>
          <div className="flex items-center gap-1 text-dashboard-muted">
            <ClockIcon className="w-4 h-4" />
            <span>{format(new Date(incident.createdAt), 'MMM d, HH:mm')}</span>
          </div>
        </div>
        {incident.assignee ? (
          <div className="flex items-center gap-1 text-dashboard-muted">
            <UserCircleIcon className="w-4 h-4" />
            <span>{incident.assignee.name}</span>
          </div>
        ) : (
          <span className="text-xs text-yellow-400">Unassigned</span>
        )}
      </div>

      {incident.slaBreach && (
        <div className="mt-2 text-xs text-red-400">
          ⚠️ SLA Breach
        </div>
      )}
    </div>
  );
}
