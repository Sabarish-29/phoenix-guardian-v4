import { format } from 'date-fns';
import {
  ExclamationTriangleIcon,
  MapPinIcon,
  ClockIcon,
  ServerIcon,
} from '@heroicons/react/24/outline';
import type { Threat } from '../../types/threat';
import clsx from 'clsx';

interface ThreatCardProps {
  threat: Threat;
  onClick: () => void;
}

const severityConfig = {
  critical: {
    bg: 'bg-threat-critical/10 border-threat-critical/30',
    badge: 'bg-threat-critical',
    icon: 'text-threat-critical',
  },
  high: {
    bg: 'bg-threat-high/10 border-threat-high/30',
    badge: 'bg-threat-high',
    icon: 'text-threat-high',
  },
  medium: {
    bg: 'bg-threat-medium/10 border-threat-medium/30',
    badge: 'bg-threat-medium text-black',
    icon: 'text-threat-medium',
  },
  low: {
    bg: 'bg-threat-low/10 border-threat-low/30',
    badge: 'bg-threat-low',
    icon: 'text-threat-low',
  },
  info: {
    bg: 'bg-threat-info/10 border-threat-info/30',
    badge: 'bg-threat-info',
    icon: 'text-threat-info',
  },
};

/**
 * Card component for displaying a threat in the feed
 */
export default function ThreatCard({ threat, onClick }: ThreatCardProps) {
  const config = severityConfig[threat.severity];
  
  return (
    <div
      onClick={onClick}
      className={clsx(
        'p-4 rounded-xl border cursor-pointer transition-all hover:scale-[1.01]',
        config.bg,
        threat.severity === 'critical' && !threat.acknowledged && 'threat-pulse-critical'
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <ExclamationTriangleIcon className={clsx('w-6 h-6 mt-0.5', config.icon)} />
          <div>
            <h3 className="text-white font-semibold">{threat.title}</h3>
            <p className="text-dashboard-muted text-sm mt-1 line-clamp-2">
              {threat.description}
            </p>
          </div>
        </div>
        <span className={clsx(
          'px-2 py-1 rounded text-xs font-bold capitalize whitespace-nowrap',
          config.badge
        )}>
          {threat.severity}
        </span>
      </div>
      
      <div className="flex flex-wrap items-center gap-4 mt-4 text-sm text-dashboard-muted">
        <div className="flex items-center gap-1">
          <MapPinIcon className="w-4 h-4" />
          <span>{threat.sourceIp}</span>
          {threat.sourceLocation?.country && (
            <span className="text-xs">({threat.sourceLocation.country})</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <ServerIcon className="w-4 h-4" />
          <span>{threat.targetAsset}</span>
        </div>
        <div className="flex items-center gap-1">
          <ClockIcon className="w-4 h-4" />
          <span>{format(new Date(threat.timestamp), 'MMM d, HH:mm:ss')}</span>
        </div>
        <span className="px-2 py-0.5 bg-dashboard-border rounded text-xs capitalize">
          {threat.attackType.replace(/_/g, ' ')}
        </span>
      </div>
      
      {threat.mitreAttackIds.length > 0 && (
        <div className="flex gap-2 mt-3">
          {threat.mitreAttackIds.slice(0, 3).map((id) => (
            <span
              key={id}
              className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs"
            >
              {id}
            </span>
          ))}
          {threat.mitreAttackIds.length > 3 && (
            <span className="text-xs text-dashboard-muted">
              +{threat.mitreAttackIds.length - 3} more
            </span>
          )}
        </div>
      )}
    </div>
  );
}
