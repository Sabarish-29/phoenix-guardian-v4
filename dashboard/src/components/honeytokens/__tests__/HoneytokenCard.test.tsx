import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import HoneytokenCard from '../HoneytokenCard';
import type { Honeytoken } from '../../../types/honeytoken';

const mockHoneytoken: Honeytoken = {
  id: 'ht-1',
  name: 'VIP Patient Record',
  type: 'patient_record',
  description: 'Decoy patient record for VIP monitoring',
  location: '/data/patients/vip',
  status: 'active',
  triggerCount: 3,
  lastTriggered: '2024-01-15T14:30:00Z',
  alertLevel: 'high',
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-15T14:30:00Z',
};

describe('HoneytokenCard', () => {
  it('renders honeytoken name', () => {
    render(<HoneytokenCard honeytoken={mockHoneytoken} />);
    expect(screen.getByText('VIP Patient Record')).toBeInTheDocument();
  });

  it('displays type with icon', () => {
    render(<HoneytokenCard honeytoken={mockHoneytoken} />);
    expect(screen.getByText('🏥')).toBeInTheDocument();
    expect(screen.getByText('patient record')).toBeInTheDocument();
  });

  it('shows status badge', () => {
    render(<HoneytokenCard honeytoken={mockHoneytoken} />);
    expect(screen.getByText('active')).toBeInTheDocument();
  });

  it('displays trigger count', () => {
    render(<HoneytokenCard honeytoken={mockHoneytoken} />);
    expect(screen.getByText('3 triggers')).toBeInTheDocument();
  });

  it('shows last triggered time', () => {
    render(<HoneytokenCard honeytoken={mockHoneytoken} />);
    expect(screen.getByText(/Last triggered:/)).toBeInTheDocument();
  });

  it('displays location', () => {
    render(<HoneytokenCard honeytoken={mockHoneytoken} />);
    expect(screen.getByText('/data/patients/vip')).toBeInTheDocument();
  });

  it('shows singular trigger for count of 1', () => {
    const singleTrigger = { ...mockHoneytoken, triggerCount: 1 };
    render(<HoneytokenCard honeytoken={singleTrigger} />);
    expect(screen.getByText('1 trigger')).toBeInTheDocument();
  });

  it('hides trigger info when count is 0', () => {
    const noTriggers = { ...mockHoneytoken, triggerCount: 0, lastTriggered: undefined };
    render(<HoneytokenCard honeytoken={noTriggers} />);
    expect(screen.queryByText(/trigger/)).not.toBeInTheDocument();
  });
});
