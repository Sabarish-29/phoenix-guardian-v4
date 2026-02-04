import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import EvidencePackageCard from '../EvidencePackageCard';
import type { EvidencePackage } from '../../../types/evidence';

const mockPackage: EvidencePackage = {
  id: 'pkg-1',
  incidentId: 'inc-1',
  incidentTitle: 'Ransomware Attack Investigation',
  status: 'ready',
  items: [
    { id: 'item-1', type: 'network_logs', name: 'network.pcap', size: 1024000, collectedAt: '2024-01-15T10:00:00Z', hash: 'abc123' },
    { id: 'item-2', type: 'system_logs', name: 'system.log', size: 512000, collectedAt: '2024-01-15T10:05:00Z', hash: 'def456' },
  ],
  totalSize: 1536000,
  createdAt: '2024-01-15T12:00:00Z',
  createdBy: 'analyst@hospital.org',
  expiresAt: '2024-02-15T12:00:00Z',
  integrityVerified: true,
  integrityVerifiedAt: '2024-01-15T12:05:00Z',
};

describe('EvidencePackageCard', () => {
  it('renders package information', () => {
    render(
      <EvidencePackageCard
        package={mockPackage}
        onDownload={() => {}}
        onVerify={() => {}}
        onViewDetails={() => {}}
      />
    );
    expect(screen.getByText('Ransomware Attack Investigation')).toBeInTheDocument();
  });

  it('displays item count', () => {
    render(
      <EvidencePackageCard
        package={mockPackage}
        onDownload={() => {}}
        onVerify={() => {}}
        onViewDetails={() => {}}
      />
    );
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('formats file size correctly', () => {
    render(
      <EvidencePackageCard
        package={mockPackage}
        onDownload={() => {}}
        onVerify={() => {}}
        onViewDetails={() => {}}
      />
    );
    expect(screen.getByText('1.5 MB')).toBeInTheDocument();
  });

  it('shows ready status', () => {
    render(
      <EvidencePackageCard
        package={mockPackage}
        onDownload={() => {}}
        onVerify={() => {}}
        onViewDetails={() => {}}
      />
    );
    expect(screen.getByText('ready')).toBeInTheDocument();
  });

  it('shows verified integrity', () => {
    render(
      <EvidencePackageCard
        package={mockPackage}
        onDownload={() => {}}
        onVerify={() => {}}
        onViewDetails={() => {}}
      />
    );
    expect(screen.getByText('Verified')).toBeInTheDocument();
  });

  it('calls onDownload when download clicked', () => {
    const onDownload = vi.fn();
    render(
      <EvidencePackageCard
        package={mockPackage}
        onDownload={onDownload}
        onVerify={() => {}}
        onViewDetails={() => {}}
      />
    );
    
    fireEvent.click(screen.getByText('Download'));
    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it('calls onViewDetails when details clicked', () => {
    const onViewDetails = vi.fn();
    render(
      <EvidencePackageCard
        package={mockPackage}
        onDownload={() => {}}
        onVerify={() => {}}
        onViewDetails={onViewDetails}
      />
    );
    
    fireEvent.click(screen.getByText('Details'));
    expect(onViewDetails).toHaveBeenCalledTimes(1);
  });

  it('shows download progress when downloading', () => {
    render(
      <EvidencePackageCard
        package={mockPackage}
        downloadProgress={{ packageId: 'pkg-1', progress: 45, status: 'downloading' }}
        onDownload={() => {}}
        onVerify={() => {}}
        onViewDetails={() => {}}
      />
    );
    expect(screen.getByText('Downloading...')).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
  });
});
