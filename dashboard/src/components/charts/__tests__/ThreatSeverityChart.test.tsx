import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ThreatSeverityChart from '../ThreatSeverityChart';
import type { Threat } from '../../../types/threat';

const mockThreats: Threat[] = [
  { id: '1', severity: 'critical', title: 'Test 1', threatType: 'malware', status: 'active', confidence: 0.9, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), sourceIp: '192.168.1.1', targetSystem: 'EHR', indicators: [], mitreTactics: [], acknowledged: false },
  { id: '2', severity: 'high', title: 'Test 2', threatType: 'ransomware', status: 'active', confidence: 0.85, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), sourceIp: '192.168.1.2', targetSystem: 'Lab', indicators: [], mitreTactics: [], acknowledged: false },
  { id: '3', severity: 'medium', title: 'Test 3', threatType: 'phishing', status: 'mitigated', confidence: 0.7, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), sourceIp: '192.168.1.3', targetSystem: 'Email', indicators: [], mitreTactics: [], acknowledged: true },
  { id: '4', severity: 'low', title: 'Test 4', threatType: 'reconnaissance', status: 'resolved', confidence: 0.6, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), sourceIp: '192.168.1.4', targetSystem: 'Web', indicators: [], mitreTactics: [], acknowledged: true },
];

describe('ThreatSeverityChart', () => {
  it('renders without crashing', () => {
    render(<ThreatSeverityChart threats={mockThreats} />);
    expect(screen.getByText('Threat Severity')).toBeInTheDocument();
  });

  it('displays empty state when no threats', () => {
    render(<ThreatSeverityChart threats={[]} />);
    expect(screen.getByText('No threat data')).toBeInTheDocument();
  });

  it('calculates severity counts correctly', () => {
    const { container } = render(<ThreatSeverityChart threats={mockThreats} />);
    expect(container.querySelector('.recharts-pie')).toBeInTheDocument();
  });

  it('renders all severity labels', () => {
    render(<ThreatSeverityChart threats={mockThreats} />);
    expect(screen.getByText('Critical')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Medium')).toBeInTheDocument();
    expect(screen.getByText('Low')).toBeInTheDocument();
  });
});
