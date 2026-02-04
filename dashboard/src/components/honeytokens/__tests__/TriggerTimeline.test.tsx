import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import TriggerTimeline from '../TriggerTimeline';
import type { HoneytokenTrigger } from '../../../types/honeytoken';

const mockTriggers: HoneytokenTrigger[] = [
  {
    id: 'trigger-1',
    honeytokenId: 'ht-1',
    honeytokenName: 'VIP Patient Record',
    timestamp: '2024-01-15T14:30:00Z',
    sourceIp: '192.168.1.100',
    sourceUser: 'suspicious_user',
    accessType: 'read',
    targetSystem: 'EHR-Database',
  },
  {
    id: 'trigger-2',
    honeytokenId: 'ht-1',
    honeytokenName: 'Admin Credential',
    timestamp: '2024-01-15T13:00:00Z',
    sourceIp: '10.0.0.50',
    accessType: 'authenticate',
    targetSystem: 'AD-Server',
  },
];

describe('TriggerTimeline', () => {
  it('renders triggers in timeline format', () => {
    render(<TriggerTimeline triggers={mockTriggers} />);
    expect(screen.getByText('VIP Patient Record')).toBeInTheDocument();
    expect(screen.getByText('Admin Credential')).toBeInTheDocument();
  });

  it('displays empty state when no triggers', () => {
    render(<TriggerTimeline triggers={[]} />);
    expect(screen.getByText('No recent triggers')).toBeInTheDocument();
  });

  it('shows source IP for each trigger', () => {
    render(<TriggerTimeline triggers={mockTriggers} />);
    expect(screen.getByText(/192.168.1.100/)).toBeInTheDocument();
    expect(screen.getByText(/10.0.0.50/)).toBeInTheDocument();
  });

  it('displays access type', () => {
    render(<TriggerTimeline triggers={mockTriggers} />);
    expect(screen.getByText(/READ access/i)).toBeInTheDocument();
    expect(screen.getByText(/AUTHENTICATE access/i)).toBeInTheDocument();
  });

  it('shows source user when available', () => {
    render(<TriggerTimeline triggers={mockTriggers} />);
    expect(screen.getByText('User: suspicious_user')).toBeInTheDocument();
  });

  it('displays target system', () => {
    render(<TriggerTimeline triggers={mockTriggers} />);
    expect(screen.getByText('EHR-Database')).toBeInTheDocument();
    expect(screen.getByText('AD-Server')).toBeInTheDocument();
  });
});
