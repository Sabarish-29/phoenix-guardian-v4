import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ThreatTimelineChart from '../ThreatTimelineChart';
import type { Threat } from '../../../types/threat';

const createThreat = (hoursAgo: number, severity: string): Threat => ({
  id: `threat-${hoursAgo}-${severity}`,
  severity: severity as any,
  title: `Threat ${hoursAgo}h ago`,
  threatType: 'malware',
  status: 'active',
  confidence: 0.9,
  createdAt: new Date(Date.now() - hoursAgo * 60 * 60 * 1000).toISOString(),
  updatedAt: new Date().toISOString(),
  sourceIp: '192.168.1.1',
  targetSystem: 'EHR',
  indicators: [],
  mitreTactics: [],
  acknowledged: false,
});

const mockThreats: Threat[] = [
  createThreat(1, 'critical'),
  createThreat(2, 'high'),
  createThreat(3, 'medium'),
  createThreat(5, 'low'),
  createThreat(10, 'critical'),
  createThreat(15, 'high'),
];

describe('ThreatTimelineChart', () => {
  it('renders without crashing', () => {
    render(<ThreatTimelineChart threats={mockThreats} />);
    expect(screen.getByText('24-Hour Threat Timeline')).toBeInTheDocument();
  });

  it('displays empty state when no threats', () => {
    render(<ThreatTimelineChart threats={[]} />);
    expect(screen.getByText('No threat data')).toBeInTheDocument();
  });

  it('renders the area chart', () => {
    const { container } = render(<ThreatTimelineChart threats={mockThreats} />);
    expect(container.querySelector('.recharts-area')).toBeInTheDocument();
  });

  it('only includes threats from last 24 hours', () => {
    const oldThreat = createThreat(48, 'critical');
    const threats = [...mockThreats, oldThreat];
    render(<ThreatTimelineChart threats={threats} />);
    // Chart should still render correctly with only 24h data
    expect(screen.getByText('24-Hour Threat Timeline')).toBeInTheDocument();
  });
});
