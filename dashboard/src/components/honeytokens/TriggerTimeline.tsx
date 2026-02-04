import { format } from 'date-fns';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import type { HoneytokenTrigger } from '../../types/honeytoken';

interface TriggerTimelineProps {
  triggers: HoneytokenTrigger[];
}

/**
 * Timeline of honeytoken trigger events
 */
export default function TriggerTimeline({ triggers }: TriggerTimelineProps) {
  if (triggers.length === 0) {
    return (
      <div className="text-center py-8 text-dashboard-muted">
        <ExclamationTriangleIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>No recent triggers</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2">
      {triggers.map((trigger) => (
        <div
          key={trigger.id}
          className="relative pl-6 pb-4 border-l-2 border-dashboard-border last:border-l-0"
        >
          <div className="absolute left-0 top-0 w-3 h-3 -translate-x-[7px] bg-red-500 rounded-full" />
          <div className="bg-dashboard-bg rounded-lg p-3">
            <div className="flex items-start justify-between mb-1">
              <span className="text-white font-medium text-sm">
                {trigger.honeytokenName}
              </span>
              <span className="text-xs text-dashboard-muted">
                {format(new Date(trigger.timestamp), 'HH:mm:ss')}
              </span>
            </div>
            <p className="text-sm text-dashboard-muted mb-2">
              {trigger.accessType.toUpperCase()} access from {trigger.sourceIp}
            </p>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="px-2 py-0.5 bg-dashboard-border rounded">
                {trigger.targetSystem}
              </span>
              {trigger.sourceUser && (
                <span className="px-2 py-0.5 bg-orange-500/20 text-orange-400 rounded">
                  User: {trigger.sourceUser}
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
