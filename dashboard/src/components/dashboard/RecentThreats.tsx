import { format } from 'date-fns';
import type { Threat } from '../../types/threat';
import clsx from 'clsx';

interface RecentThreatsProps {
  threats: Threat[];
}

const severityColors = {
  critical: 'bg-threat-critical',
  high: 'bg-threat-high',
  medium: 'bg-threat-medium',
  low: 'bg-threat-low',
  info: 'bg-threat-info',
};

/**
 * List of recent threats for dashboard
 */
export default function RecentThreats({ threats }: RecentThreatsProps) {
  if (threats.length === 0) {
    return (
      <div className="text-center py-8 text-dashboard-muted">
        No recent threats
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {threats.map((threat) => (
        <div
          key={threat.id}
          className="flex items-start gap-3 p-3 rounded-lg bg-dashboard-bg/50 hover:bg-dashboard-bg transition-colors cursor-pointer"
        >
          <div className={clsx(
            'w-2 h-2 mt-2 rounded-full flex-shrink-0',
            severityColors[threat.severity]
          )} />
          <div className="flex-1 min-w-0">
            <p className="text-white font-medium truncate">{threat.title}</p>
            <p className="text-sm text-dashboard-muted truncate">{threat.description}</p>
            <div className="flex items-center gap-2 mt-1 text-xs text-dashboard-muted">
              <span>{threat.attackType.replace('_', ' ')}</span>
              <span>•</span>
              <span>{format(new Date(threat.timestamp), 'HH:mm')}</span>
            </div>
          </div>
          <span className={clsx(
            'px-2 py-0.5 rounded text-xs font-medium capitalize',
            threat.severity === 'critical' ? 'bg-threat-critical/20 text-red-400' :
            threat.severity === 'high' ? 'bg-threat-high/20 text-orange-400' :
            threat.severity === 'medium' ? 'bg-threat-medium/20 text-yellow-400' :
            'bg-threat-low/20 text-green-400'
          )}>
            {threat.severity}
          </span>
        </div>
      ))}
    </div>
  );
}
