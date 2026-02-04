import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import SignatureList from '../SignatureList';
import type { ThreatSignature } from '../../../types/federated';

const mockSignatures: ThreatSignature[] = [
  {
    id: 'sig-1',
    signatureHash: 'abc123def456ghi789jkl012mno345',
    attackType: 'ransomware_encryption',
    confidence: 0.95,
    contributorCount: 15,
    firstSeen: '2024-01-01T00:00:00Z',
    lastUpdated: '2024-01-15T12:00:00Z',
    mitreMapping: ['T1486', 'T1059'],
    privacyPreserved: true,
  },
  {
    id: 'sig-2',
    signatureHash: 'xyz789uvw012rst345abc678def901',
    attackType: 'lateral_movement',
    confidence: 0.82,
    contributorCount: 8,
    firstSeen: '2024-01-10T00:00:00Z',
    lastUpdated: '2024-01-14T18:00:00Z',
    mitreMapping: ['T1021'],
    privacyPreserved: true,
  },
];

describe('SignatureList', () => {
  it('renders signature list', () => {
    render(<SignatureList signatures={mockSignatures} />);
    expect(screen.getByText(/abc123def456/)).toBeInTheDocument();
  });

  it('displays empty state when no signatures', () => {
    render(<SignatureList signatures={[]} />);
    expect(screen.getByText('No threat signatures available')).toBeInTheDocument();
  });

  it('shows attack types', () => {
    render(<SignatureList signatures={mockSignatures} />);
    expect(screen.getByText('ransomware encryption')).toBeInTheDocument();
    expect(screen.getByText('lateral movement')).toBeInTheDocument();
  });

  it('displays confidence percentages', () => {
    render(<SignatureList signatures={mockSignatures} />);
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
  });

  it('shows contributor count', () => {
    render(<SignatureList signatures={mockSignatures} />);
    expect(screen.getByText('15 contributors')).toBeInTheDocument();
    expect(screen.getByText('8 contributors')).toBeInTheDocument();
  });

  it('displays MITRE mappings', () => {
    render(<SignatureList signatures={mockSignatures} />);
    expect(screen.getByText('T1486')).toBeInTheDocument();
    expect(screen.getByText('T1059')).toBeInTheDocument();
    expect(screen.getByText('T1021')).toBeInTheDocument();
  });

  it('shows DP Protected badge for privacy-preserved signatures', () => {
    render(<SignatureList signatures={mockSignatures} />);
    expect(screen.getAllByText('DP Protected')).toHaveLength(2);
  });

  it('displays first seen date', () => {
    render(<SignatureList signatures={mockSignatures} />);
    expect(screen.getByText(/First seen: Jan 1/)).toBeInTheDocument();
    expect(screen.getByText(/First seen: Jan 10/)).toBeInTheDocument();
  });
});
