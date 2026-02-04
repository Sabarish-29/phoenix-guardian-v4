import { useEffect, useState } from 'react';
import {
  FolderArrowDownIcon,
  ShieldCheckIcon,
  ClockIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline';
import { useAppDispatch, useAppSelector } from '../hooks/useStore';
import {
  fetchEvidencePackages,
  selectAllPackages,
  selectEvidenceLoading,
  selectDownloads,
  downloadEvidencePackage,
  verifyEvidenceIntegrity,
} from '../store/slices/evidenceSlice';
import EvidencePackageCard from '../components/evidence/EvidencePackageCard';
import EvidenceDetailModal from '../components/evidence/EvidenceDetailModal';
import type { EvidencePackage } from '../types/evidence';
import { format } from 'date-fns';

/**
 * Evidence - Court-ready evidence package management
 */
export default function Evidence() {
  const dispatch = useAppDispatch();
  const packages = useAppSelector(selectAllPackages);
  const loading = useAppSelector(selectEvidenceLoading);
  const downloads = useAppSelector(selectDownloads);
  
  const [selectedPackage, setSelectedPackage] = useState<EvidencePackage | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'ready' | 'generating'>('all');

  useEffect(() => {
    dispatch(fetchEvidencePackages(undefined));
  }, [dispatch]);

  const filteredPackages = packages.filter((pkg) => {
    if (statusFilter === 'ready' && pkg.status !== 'ready') return false;
    if (statusFilter === 'generating' && pkg.status !== 'generating') return false;
    return true;
  });

  const handleDownload = (packageId: string) => {
    dispatch(downloadEvidencePackage(packageId));
  };

  const handleVerify = (packageId: string) => {
    dispatch(verifyEvidenceIntegrity(packageId));
  };

  // Stats
  const readyCount = packages.filter(p => p.status === 'ready').length;
  const generatingCount = packages.filter(p => p.status === 'generating').length;
  const totalSize = packages.reduce((sum, p) => sum + p.totalSize, 0);

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  return (
    <div className="space-y-6">
      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <FolderArrowDownIcon className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Total Packages</p>
              <p className="text-xl font-bold text-white">{packages.length}</p>
            </div>
          </div>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <ShieldCheckIcon className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Ready</p>
              <p className="text-xl font-bold text-white">{readyCount}</p>
            </div>
          </div>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-500/20 rounded-lg">
              <ClockIcon className="w-5 h-5 text-yellow-400" />
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Generating</p>
              <p className="text-xl font-bold text-white">{generatingCount}</p>
            </div>
          </div>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <ArrowDownTrayIcon className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Total Size</p>
              <p className="text-xl font-bold text-white">{formatBytes(totalSize)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {(['all', 'ready', 'generating'] as const).map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
              statusFilter === status
                ? 'bg-phoenix-500/20 text-phoenix-400 border border-phoenix-500'
                : 'bg-dashboard-card border border-dashboard-border text-dashboard-muted hover:text-white'
            }`}
          >
            {status}
          </button>
        ))}
      </div>

      {/* Package List */}
      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-32 skeleton rounded-xl" />
          ))}
        </div>
      ) : filteredPackages.length === 0 ? (
        <div className="text-center py-12 bg-dashboard-card rounded-xl border border-dashboard-border">
          <FolderArrowDownIcon className="w-12 h-12 mx-auto text-dashboard-muted mb-4" />
          <p className="text-dashboard-muted">No evidence packages available</p>
          <p className="text-sm text-dashboard-muted mt-1">
            Generate packages from the Incidents page
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredPackages.map((pkg) => (
            <EvidencePackageCard
              key={pkg.id}
              package={pkg}
              downloadProgress={downloads[pkg.id]}
              onDownload={() => handleDownload(pkg.id)}
              onVerify={() => handleVerify(pkg.id)}
              onViewDetails={() => setSelectedPackage(pkg)}
            />
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {selectedPackage && (
        <EvidenceDetailModal
          package={selectedPackage}
          onClose={() => setSelectedPackage(null)}
        />
      )}
    </div>
  );
}
