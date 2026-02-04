import { useState } from 'react';
import { XMarkIcon, CheckIcon, FolderPlusIcon } from '@heroicons/react/24/outline';
import { format } from 'date-fns';
import { useAppDispatch } from '../../hooks/useStore';
import { acknowledgeThreat } from '../../store/slices/threatsSlice';
import type { Threat } from '../../types/threat';
import clsx from 'clsx';

interface ThreatDetailModalProps {
  threat: Threat;
  onClose: () => void;
}

const severityColors = {
  critical: 'bg-threat-critical',
  high: 'bg-threat-high',
  medium: 'bg-threat-medium',
  low: 'bg-threat-low',
  info: 'bg-threat-info',
};

/**
 * Modal for viewing threat details
 */
export default function ThreatDetailModal({ threat, onClose }: ThreatDetailModalProps) {
  const dispatch = useAppDispatch();
  const [acknowledging, setAcknowledging] = useState(false);

  const handleAcknowledge = async () => {
    setAcknowledging(true);
    try {
      await dispatch(acknowledgeThreat(threat.id));
    } finally {
      setAcknowledging(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-dashboard-card rounded-xl border border-dashboard-border w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b border-dashboard-border">
          <div className="flex items-center gap-3">
            <span className={clsx(
              'px-2 py-1 rounded text-xs font-bold capitalize text-white',
              severityColors[threat.severity]
            )}>
              {threat.severity}
            </span>
            <h2 className="text-lg font-semibold text-white">{threat.title}</h2>
          </div>
          <button onClick={onClose} className="text-dashboard-muted hover:text-white">
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto max-h-[60vh]">
          <p className="text-dashboard-text mb-6">{threat.description}</p>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <label className="text-sm text-dashboard-muted">Source IP</label>
              <p className="text-white font-mono">{threat.sourceIp}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Target Asset</label>
              <p className="text-white">{threat.targetAsset}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Attack Type</label>
              <p className="text-white capitalize">{threat.attackType.replace(/_/g, ' ')}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Confidence</label>
              <p className="text-white">{(threat.confidence * 100).toFixed(0)}%</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Detected</label>
              <p className="text-white">{format(new Date(threat.timestamp), 'PPpp')}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Status</label>
              <p className={threat.acknowledged ? 'text-green-400' : 'text-yellow-400'}>
                {threat.acknowledged ? 'Acknowledged' : 'Pending Review'}
              </p>
            </div>
          </div>

          {/* Indicators */}
          {threat.indicators.length > 0 && (
            <div className="mb-6">
              <label className="text-sm text-dashboard-muted mb-2 block">Indicators of Compromise</label>
              <div className="bg-dashboard-bg rounded-lg p-3 font-mono text-sm">
                {threat.indicators.map((indicator, idx) => (
                  <div key={idx} className="text-dashboard-text">{indicator}</div>
                ))}
              </div>
            </div>
          )}

          {/* MITRE ATT&CK */}
          {threat.mitreAttackIds.length > 0 && (
            <div className="mb-6">
              <label className="text-sm text-dashboard-muted mb-2 block">MITRE ATT&CK Techniques</label>
              <div className="flex flex-wrap gap-2">
                {threat.mitreAttackIds.map((id) => (
                  <a
                    key={id}
                    href={`https://attack.mitre.org/techniques/${id.replace('.', '/')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-sm hover:bg-purple-500/30"
                  >
                    {id}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-4 border-t border-dashboard-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-dashboard-muted hover:text-white transition-colors"
          >
            Close
          </button>
          <button
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            <FolderPlusIcon className="w-5 h-5" />
            Create Incident
          </button>
          {!threat.acknowledged && (
            <button
              onClick={handleAcknowledge}
              disabled={acknowledging}
              className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors disabled:opacity-50"
            >
              <CheckIcon className="w-5 h-5" />
              {acknowledging ? 'Acknowledging...' : 'Acknowledge'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
