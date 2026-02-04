import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import EvidenceDetailModal from '../EvidenceDetailModal';
import type { EvidencePackage } from '../../../types/evidence';

const mockPackage: EvidencePackage = {
  id: 'pkg-1',
  incidentId: 'inc-1',
  incidentTitle: 'Ransomware Attack Investigation',
  status: 'ready',
  items: [
    { id: 'item-1', type: 'network_logs', name: 'network.pcap', size: 1024000, collectedAt: '2024-01-15T10:00:00Z', hash: 'abc123def456' },
    { id: 'item-2', type: 'system_logs', name: 'system.log', size: 512000, collectedAt: '2024-01-15T10:05:00Z', hash: 'ghi789jkl012' },
    { id: 'item-3', type: 'memory_dump', name: 'memory.dmp', size: 2048000, collectedAt: '2024-01-15T10:10:00Z', hash: 'mno345pqr678' },
  ],
  totalSize: 3584000,
  createdAt: '2024-01-15T12:00:00Z',
  createdBy: 'analyst@hospital.org',
  expiresAt: '2024-02-15T12:00:00Z',
  integrityVerified: true,
  integrityVerifiedAt: '2024-01-15T12:05:00Z',
};

describe('EvidenceDetailModal', () => {
  it('renders package details', () => {
    render(<EvidenceDetailModal package={mockPackage} onClose={() => {}} />);
    expect(screen.getByText('Evidence Package Details')).toBeInTheDocument();
  });

  it('displays incident title', () => {
    render(<EvidenceDetailModal package={mockPackage} onClose={() => {}} />);
    expect(screen.getByText('Ransomware Attack Investigation')).toBeInTheDocument();
  });

  it('shows created by information', () => {
    render(<EvidenceDetailModal package={mockPackage} onClose={() => {}} />);
    expect(screen.getByText('analyst@hospital.org')).toBeInTheDocument();
  });

  it('displays integrity status', () => {
    render(<EvidenceDetailModal package={mockPackage} onClose={() => {}} />);
    expect(screen.getByText('Integrity Verified')).toBeInTheDocument();
  });

  it('lists all evidence items', () => {
    render(<EvidenceDetailModal package={mockPackage} onClose={() => {}} />);
    expect(screen.getByText('network.pcap')).toBeInTheDocument();
    expect(screen.getByText('system.log')).toBeInTheDocument();
    expect(screen.getByText('memory.dmp')).toBeInTheDocument();
  });

  it('shows item count in header', () => {
    render(<EvidenceDetailModal package={mockPackage} onClose={() => {}} />);
    expect(screen.getByText('Evidence Items (3)')).toBeInTheDocument();
  });

  it('displays item types', () => {
    render(<EvidenceDetailModal package={mockPackage} onClose={() => {}} />);
    expect(screen.getByText('Network Logs')).toBeInTheDocument();
    expect(screen.getByText('System Logs')).toBeInTheDocument();
    expect(screen.getByText('Memory Dump')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    render(<EvidenceDetailModal package={mockPackage} onClose={onClose} />);
    
    fireEvent.click(screen.getByText('Close'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
