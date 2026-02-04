import { format } from 'date-fns';
import {
  ArrowDownTrayIcon,
  ShieldCheckIcon,
  EyeIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import type { EvidencePackage, DownloadProgress } from '../../types/evidence';
import clsx from 'clsx';

interface EvidencePackageCardProps {
  package: EvidencePackage;
  downloadProgress?: DownloadProgress;
  onDownload: () => void;
  onVerify: () => void;
  onViewDetails: () => void;
}

const statusColors = {
  generating: 'text-yellow-400 bg-yellow-400/20',
  ready: 'text-green-400 bg-green-400/20',
  expired: 'text-red-400 bg-red-400/20',
  error: 'text-red-400 bg-red-400/20',
};

/**
 * Card for displaying an evidence package
 */
export default function EvidencePackageCard({
  package: pkg,
  downloadProgress,
  onDownload,
  onVerify,
  onViewDetails,
}: EvidencePackageCardProps) {
  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const isDownloading = downloadProgress?.status === 'downloading';

  return (
    <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h4 className="text-white font-medium">{pkg.incidentTitle}</h4>
          <p className="text-sm text-dashboard-muted">
            Package ID: {pkg.id.slice(0, 8)}
          </p>
        </div>
        <span className={clsx(
          'px-2 py-0.5 rounded text-xs font-medium capitalize',
          statusColors[pkg.status]
        )}>
          {pkg.status}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 text-sm">
        <div>
          <span className="text-dashboard-muted">Items</span>
          <p className="text-white">{pkg.items.length}</p>
        </div>
        <div>
          <span className="text-dashboard-muted">Size</span>
          <p className="text-white">{formatBytes(pkg.totalSize)}</p>
        </div>
        <div>
          <span className="text-dashboard-muted">Created</span>
          <p className="text-white">{format(new Date(pkg.createdAt), 'MMM d, HH:mm')}</p>
        </div>
        <div>
          <span className="text-dashboard-muted">Integrity</span>
          <p className={pkg.integrityVerified ? 'text-green-400' : 'text-yellow-400'}>
            {pkg.integrityVerified ? 'Verified' : 'Pending'}
          </p>
        </div>
      </div>

      {/* Download Progress */}
      {isDownloading && (
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-dashboard-muted">Downloading...</span>
            <span className="text-white">{downloadProgress.progress}%</span>
          </div>
          <div className="h-2 bg-dashboard-border rounded-full overflow-hidden">
            <div
              className="h-full bg-phoenix-500 transition-all duration-300"
              style={{ width: `${downloadProgress.progress}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={onViewDetails}
          className="flex items-center gap-1 px-3 py-1.5 text-sm text-dashboard-muted hover:text-white transition-colors"
        >
          <EyeIcon className="w-4 h-4" />
          Details
        </button>
        {pkg.status === 'ready' && (
          <>
            <button
              onClick={onVerify}
              disabled={pkg.integrityVerified}
              className="flex items-center gap-1 px-3 py-1.5 text-sm text-dashboard-muted hover:text-white transition-colors disabled:opacity-50"
            >
              <ShieldCheckIcon className="w-4 h-4" />
              Verify
            </button>
            <button
              onClick={onDownload}
              disabled={isDownloading}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-phoenix-500 text-white rounded hover:bg-phoenix-600 transition-colors disabled:opacity-50 ml-auto"
            >
              <ArrowDownTrayIcon className="w-4 h-4" />
              Download
            </button>
          </>
        )}
        {pkg.status === 'generating' && (
          <div className="flex items-center gap-1 ml-auto text-sm text-yellow-400">
            <ClockIcon className="w-4 h-4 animate-spin" />
            Generating...
          </div>
        )}
      </div>
    </div>
  );
}
