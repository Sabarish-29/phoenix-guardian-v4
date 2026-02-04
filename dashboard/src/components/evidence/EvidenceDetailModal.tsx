import { XMarkIcon, DocumentIcon, ShieldCheckIcon } from '@heroicons/react/24/outline';
import { format } from 'date-fns';
import type { EvidencePackage } from '../../types/evidence';

interface EvidenceDetailModalProps {
  package: EvidencePackage;
  onClose: () => void;
}

const typeLabels: Record<string, string> = {
  network_logs: 'Network Logs',
  system_logs: 'System Logs',
  application_logs: 'Application Logs',
  memory_dump: 'Memory Dump',
  disk_image: 'Disk Image',
  screenshots: 'Screenshots',
  network_capture: 'Network Capture',
  malware_sample: 'Malware Sample',
  timeline: 'Timeline',
  report: 'Report',
};

/**
 * Modal showing evidence package details
 */
export default function EvidenceDetailModal({ package: pkg, onClose }: EvidenceDetailModalProps) {
  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-dashboard-card rounded-xl border border-dashboard-border w-full max-w-2xl max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-dashboard-border">
          <h2 className="text-lg font-semibold text-white">Evidence Package Details</h2>
          <button onClick={onClose} className="text-dashboard-muted hover:text-white">
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <div className="p-4 overflow-y-auto max-h-[70vh]">
          {/* Package Info */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <label className="text-sm text-dashboard-muted">Incident</label>
              <p className="text-white">{pkg.incidentTitle}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Created By</label>
              <p className="text-white">{pkg.createdBy}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Created At</label>
              <p className="text-white">{format(new Date(pkg.createdAt), 'PPpp')}</p>
            </div>
            <div>
              <label className="text-sm text-dashboard-muted">Expires At</label>
              <p className="text-white">{format(new Date(pkg.expiresAt), 'PPpp')}</p>
            </div>
          </div>

          {/* Integrity Status */}
          <div className="flex items-center gap-3 p-3 rounded-lg bg-dashboard-bg mb-6">
            <ShieldCheckIcon className={`w-6 h-6 ${pkg.integrityVerified ? 'text-green-400' : 'text-yellow-400'}`} />
            <div>
              <p className="text-white font-medium">
                {pkg.integrityVerified ? 'Integrity Verified' : 'Pending Verification'}
              </p>
              {pkg.integrityVerifiedAt && (
                <p className="text-sm text-dashboard-muted">
                  Verified at {format(new Date(pkg.integrityVerifiedAt), 'PPpp')}
                </p>
              )}
            </div>
          </div>

          {/* Evidence Items */}
          <h3 className="text-white font-medium mb-3">Evidence Items ({pkg.items.length})</h3>
          <div className="space-y-2">
            {pkg.items.map((item) => (
              <div key={item.id} className="flex items-center gap-3 p-3 bg-dashboard-bg rounded-lg">
                <DocumentIcon className="w-5 h-5 text-dashboard-muted" />
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm truncate">{item.name}</p>
                  <p className="text-xs text-dashboard-muted">
                    {typeLabels[item.type] || item.type} • {formatBytes(item.size)}
                  </p>
                </div>
                <span className="text-xs text-dashboard-muted">
                  {format(new Date(item.collectedAt), 'MMM d, HH:mm')}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end p-4 border-t border-dashboard-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-dashboard-muted hover:text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
