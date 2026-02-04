import { FingerPrintIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { format } from 'date-fns';
import type { Honeytoken } from '../../types/honeytoken';
import clsx from 'clsx';

interface HoneytokenCardProps {
  honeytoken: Honeytoken;
}

const typeIcons = {
  patient_record: '🏥',
  medication: '💊',
  admin_credential: '🔐',
  api_key: '🔑',
  database: '🗄️',
};

const statusColors = {
  active: 'text-green-400 bg-green-400/20',
  inactive: 'text-gray-400 bg-gray-400/20',
  expired: 'text-red-400 bg-red-400/20',
};

/**
 * Card displaying a honeytoken
 */
export default function HoneytokenCard({ honeytoken }: HoneytokenCardProps) {
  return (
    <div className="bg-dashboard-bg rounded-xl border border-dashboard-border p-4 hover:border-phoenix-500/50 transition-colors cursor-pointer">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">{typeIcons[honeytoken.type]}</span>
          <div>
            <h4 className="text-white font-medium">{honeytoken.name}</h4>
            <p className="text-xs text-dashboard-muted capitalize">
              {honeytoken.type.replace(/_/g, ' ')}
            </p>
          </div>
        </div>
        <span className={clsx(
          'px-2 py-0.5 rounded text-xs font-medium capitalize',
          statusColors[honeytoken.status]
        )}>
          {honeytoken.status}
        </span>
      </div>

      <p className="text-sm text-dashboard-muted mb-3 line-clamp-2">
        {honeytoken.description}
      </p>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-1 text-dashboard-muted">
          <FingerPrintIcon className="w-4 h-4" />
          <span>{honeytoken.location}</span>
        </div>
        {honeytoken.triggerCount > 0 && (
          <div className="flex items-center gap-1 text-red-400">
            <ExclamationTriangleIcon className="w-4 h-4" />
            <span>{honeytoken.triggerCount} trigger{honeytoken.triggerCount !== 1 ? 's' : ''}</span>
          </div>
        )}
      </div>

      {honeytoken.lastTriggered && (
        <p className="text-xs text-dashboard-muted mt-2">
          Last triggered: {format(new Date(honeytoken.lastTriggered), 'MMM d, HH:mm')}
        </p>
      )}
    </div>
  );
}
