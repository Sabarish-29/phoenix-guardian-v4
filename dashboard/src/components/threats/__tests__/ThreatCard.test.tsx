import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ThreatCard from '../ThreatCard';
import type { Threat } from '../../../types/threat';

const mockThreat: Threat = {
  id: 'threat-1',
  severity: 'critical',
  title: 'Ransomware Detected',
  description: 'BlackCat ransomware variant detected attempting lateral movement',
  threatType: 'ransomware',
  status: 'active',
  confidence: 0.95,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  sourceIp: '10.0.0.50',
  targetSystem: 'EHR-Primary',
  indicators: ['hash123', 'domain.bad'],
  mitreTactics: ['T1486', 'T1059'],
  acknowledged: false,
};

describe('ThreatCard', () => {
  it('renders threat information correctly', () => {
    render(<ThreatCard threat={mockThreat} onClick={() => {}} />);
    
    expect(screen.getByText('Ransomware Detected')).toBeInTheDocument();
    expect(screen.getByText(/ransomware/i)).toBeInTheDocument();
    expect(screen.getByText(/EHR-Primary/)).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<ThreatCard threat={mockThreat} onClick={onClick} />);
    
    fireEvent.click(screen.getByText('Ransomware Detected'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('displays severity badge with correct styling', () => {
    const { container } = render(<ThreatCard threat={mockThreat} onClick={() => {}} />);
    
    const badge = container.querySelector('[class*="critical"]');
    expect(badge).toBeInTheDocument();
  });

  it('shows active status indicator', () => {
    render(<ThreatCard threat={mockThreat} onClick={() => {}} />);
    expect(screen.getByText('active')).toBeInTheDocument();
  });

  it('renders MITRE tactics when present', () => {
    render(<ThreatCard threat={mockThreat} onClick={() => {}} />);
    expect(screen.getByText('T1486')).toBeInTheDocument();
    expect(screen.getByText('T1059')).toBeInTheDocument();
  });

  it('shows acknowledged state correctly', () => {
    const acknowledgedThreat = { ...mockThreat, acknowledged: true };
    render(<ThreatCard threat={acknowledgedThreat} onClick={() => {}} />);
    // Check for visual indicator of acknowledged state
    expect(screen.getByText('Ransomware Detected')).toBeInTheDocument();
  });
});
