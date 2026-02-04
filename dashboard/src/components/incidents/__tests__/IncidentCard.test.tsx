import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import IncidentCard from '../IncidentCard';
import type { Incident } from '../../../types/incident';

const mockIncident: Incident = {
  id: 'inc-1',
  title: 'Ransomware Attack on EHR System',
  description: 'BlackCat ransomware detected attempting to encrypt patient records',
  priority: 'P1',
  severity: 'critical',
  status: 'investigating',
  category: 'ransomware',
  affectedAssets: ['EHR-Primary', 'EHR-Backup'],
  affectedDepartments: ['Radiology', 'Emergency'],
  threatIds: ['threat-1'],
  assignee: { id: 'user-1', name: 'John Analyst', email: 'john@hospital.org' },
  createdAt: '2024-01-15T10:00:00Z',
  updatedAt: '2024-01-15T12:00:00Z',
  slaBreach: false,
  containmentActions: ['Network isolation'],
  remediationActions: [],
};

describe('IncidentCard', () => {
  it('renders incident title', () => {
    render(<IncidentCard incident={mockIncident} onClick={() => {}} />);
    expect(screen.getByText('Ransomware Attack on EHR System')).toBeInTheDocument();
  });

  it('displays priority badge', () => {
    render(<IncidentCard incident={mockIncident} onClick={() => {}} />);
    expect(screen.getByText('P1')).toBeInTheDocument();
  });

  it('shows status', () => {
    render(<IncidentCard incident={mockIncident} onClick={() => {}} />);
    expect(screen.getByText('investigating')).toBeInTheDocument();
  });

  it('displays category', () => {
    render(<IncidentCard incident={mockIncident} onClick={() => {}} />);
    expect(screen.getByText('ransomware')).toBeInTheDocument();
  });

  it('shows assignee name', () => {
    render(<IncidentCard incident={mockIncident} onClick={() => {}} />);
    expect(screen.getByText('John Analyst')).toBeInTheDocument();
  });

  it('shows unassigned when no assignee', () => {
    const unassignedIncident = { ...mockIncident, assignee: undefined };
    render(<IncidentCard incident={unassignedIncident} onClick={() => {}} />);
    expect(screen.getByText('Unassigned')).toBeInTheDocument();
  });

  it('displays SLA breach warning', () => {
    const breachedIncident = { ...mockIncident, slaBreach: true };
    render(<IncidentCard incident={breachedIncident} onClick={() => {}} />);
    expect(screen.getByText('⚠️ SLA Breach')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<IncidentCard incident={mockIncident} onClick={onClick} />);
    
    fireEvent.click(screen.getByText('Ransomware Attack on EHR System'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('applies correct priority colors', () => {
    const { container } = render(<IncidentCard incident={mockIncident} onClick={() => {}} />);
    expect(container.querySelector('[class*="red"]')).toBeInTheDocument();
  });
});
